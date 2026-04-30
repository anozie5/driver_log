from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.db.models import Q
import datetime

from logApi.models import DayLog, ActLog
from logApi.serializers import (
    DayLogListSerializer,
    DayLogDetailSerializer,
    ActLogSerializer,
    CoDriverApprovalSerializer,
)
from logApi.utils import (
    get_or_create_day_log,
    submit_co_driver_link,
    approve_co_driver_log,
)
from logApi.exceptions import TimeRangeOverlapError, InvalidTimeRangeError, PermissionDeniedError


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def _is_manager(user):
    return user.is_manager


def _driver_or_manager(user):
    return user.is_driver or _is_manager(user)


# ---------------------------------------------------------------------------
# DayLog views
# ---------------------------------------------------------------------------

class DayLogListView(APIView):
    """
    GET  /logs/
        Drivers  → their own logs only.
        Managers → all logs, with optional filters.

    Query params:
        driver_id   — filter by a specific driver's PK  (managers only)
        date        — exact day        YYYY-MM-DD
        week        — ISO week number  ?week=22&year=2025
        year        — calendar year    ?year=2025
        month       — calendar month   ?month=6&year=2025
        period      — shorthand: today | this_week | this_month | this_year

    POST /logs/
        Create a new DayLog for the authenticated driver.
        Managers may create logs on behalf of drivers by including { "user_id": <pk> }
        in the request body (not exposed in the serializer — handled here explicitly).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _driver_or_manager(request.user):
            return Response({'detail': 'Drivers or managers only.'}, status=status.HTTP_403_FORBIDDEN)

        qs = DayLog.objects.select_related('user', 'co_driver')

        # Scope to own logs unless manager
        if not _is_manager(request.user):
            qs = qs.filter(user=request.user)
        else:
            driver_id = request.query_params.get('driver_id')
            if driver_id:
                qs = qs.filter(user_id=driver_id)

        # --- Date filters ---
        today = datetime.date.today()
        period = request.query_params.get('period')

        if period == 'today':
            qs = qs.filter(day=today)
        elif period == 'this_week':
            start = today - datetime.timedelta(days=today.weekday())
            qs = qs.filter(day__gte=start, day__lte=today)
        elif period == 'this_month':
            qs = qs.filter(day__year=today.year, day__month=today.month)
        elif period == 'this_year':
            qs = qs.filter(day__year=today.year)
        else:
            date_str = request.query_params.get('date')
            week_str = request.query_params.get('week')
            month_str = request.query_params.get('month')
            year_str = request.query_params.get('year')

            if date_str:
                parsed = parse_date(date_str)
                if not parsed:
                    return Response({'detail': 'Invalid date. Use YYYY-MM-DD.'}, status=400)
                qs = qs.filter(day=parsed)
            elif week_str:
                try:
                    year = int(year_str or today.year)
                    week = int(week_str)
                    # ISO week: Monday is day 1
                    week_start = datetime.date.fromisocalendar(year, week, 1)
                    week_end = week_start + datetime.timedelta(days=6)
                    qs = qs.filter(day__gte=week_start, day__lte=week_end)
                except (ValueError, TypeError):
                    return Response({'detail': 'Invalid week/year.'}, status=400)
            elif month_str:
                try:
                    year = int(year_str or today.year)
                    month = int(month_str)
                    qs = qs.filter(day__year=year, day__month=month)
                except (ValueError, TypeError):
                    return Response({'detail': 'Invalid month/year.'}, status=400)
            elif year_str:
                try:
                    qs = qs.filter(day__year=int(year_str))
                except (ValueError, TypeError):
                    return Response({'detail': 'Invalid year.'}, status=400)

        serializer = DayLogListSerializer(qs.order_by('day'), many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_driver and not _is_manager(request.user):
            return Response({'detail': 'Only drivers or managers can create logs.'}, status=403)

        serializer = DayLogDetailSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # Managers can create on behalf of a driver
        day_log_user = request.user
        if _is_manager(request.user):
            user_id = request.data.get('user_id')
            if user_id:
                from authApi.models import User
                day_log_user = get_object_or_404(User, pk=user_id, is_driver=True)

        day_obj = serializer.validated_data.get('day')
        _, created = get_or_create_day_log(day_log_user, day_obj)
        if not created:
            return Response(
                {'detail': f'A log for {day_obj} already exists for this driver.'},
                status=status.HTTP_409_CONFLICT,
            )

        log = serializer.save(user=day_log_user)
        return Response(DayLogDetailSerializer(log, context={'request': request}).data, status=201)


class DayLogDetailView(APIView):
    """
    GET    /logs/<pk>/   → retrieve a specific DayLog (with all act_logs embedded)
    PATCH  /logs/<pk>/   → update header fields / totals
    DELETE /logs/<pk>/   → delete (cascades to act_logs)
    """

    permission_classes = [IsAuthenticated]

    def _get_log(self, request, pk):
        """Return the log if the requester is its owner or a manager."""
        log = get_object_or_404(DayLog.objects.select_related('user', 'co_driver'), pk=pk)
        if not _is_manager(request.user) and log.user != request.user:
            return None, Response({'detail': 'Not found.'}, status=404)
        return log, None

    def get(self, request, pk):
        log, err = self._get_log(request, pk)
        if err:
            return err
        return Response(DayLogDetailSerializer(log, context={'request': request}).data)

    def patch(self, request, pk):
        log, err = self._get_log(request, pk)
        if err:
            return err
        serializer = DayLogDetailSerializer(log, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(DayLogDetailSerializer(log, context={'request': request}).data)

    def delete(self, request, pk):
        log, err = self._get_log(request, pk)
        if err:
            return err
        if not _is_manager(request.user) and log.user != request.user:
            return Response({'detail': 'Permission denied.'}, status=403)
        log.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Co-driver workflow
# ---------------------------------------------------------------------------

class CoDriverSubmitView(APIView):
    """
    POST /logs/<co_driver_log_id>/submit-co-driver/
    Body: { "primary_log_id": <int> }

    The co-driver submits their completed DayLog to be linked to the main
    driver's log for the same day. Status becomes "pending" until the main
    driver approves or rejects.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        co_log = get_object_or_404(DayLog, pk=pk, user=request.user)
        primary_log_id = request.data.get('primary_log_id')
        if not primary_log_id:
            return Response({'detail': 'primary_log_id is required.'}, status=400)

        primary_log = get_object_or_404(DayLog, pk=primary_log_id)

        try:
            submit_co_driver_link(co_log, primary_log)
        except InvalidTimeRangeError as exc:
            return Response({'detail': exc.detail}, status=exc.status_code)

        return Response(
            {
                'detail': 'Submitted for approval.',
                'co_driver_log_id': co_log.pk,
                'primary_log_id': primary_log.pk,
                'status': 'pending',
            },
            status=status.HTTP_200_OK,
        )


class CoDriverApprovalView(APIView):
    """
    PATCH /logs/<primary_log_id>/approve-co-driver/
    Body: { "co_driver_log_id": <int>, "approve": true|false }

    Only the owner of the primary log (the main driver) can call this.
    On approval, the co_driver FK on the primary log is set automatically.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        primary_log = get_object_or_404(DayLog, pk=pk, user=request.user)

        serializer = CoDriverApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        co_log = get_object_or_404(DayLog, pk=serializer.validated_data['co_driver_log_id'])
        approve = serializer.validated_data['approve']

        try:
            approve_co_driver_log(primary_log, co_log, approve)
        except PermissionDeniedError as exc:
            return Response({'detail': exc.detail}, status=exc.status_code)

        return Response(
            {
                'detail': 'approved' if approve else 'rejected',
                'co_driver_log_id': co_log.pk,
                'primary_log_id': primary_log.pk,
                'approve': approve,
            }
        )


class PendingCoDriverView(APIView):
    """
    GET /logs/pending-co-drivers/
    Returns all co-driver submissions awaiting approval by the current driver.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        pending = DayLog.objects.filter(
            linked_primary_log__user=request.user,
            is_co_driver_entry=True,
            co_driver_approved__isnull=True,
        ).select_related('user', 'linked_primary_log')

        return Response(DayLogListSerializer(pending, many=True).data)


# ---------------------------------------------------------------------------
# ActLog views
# ---------------------------------------------------------------------------

class ActLogListView(APIView):
    """
    GET  /logs/<day_log_id>/acts/       → list all acts for a DayLog
    POST /logs/<day_log_id>/acts/       → add a new act to the DayLog
    """

    permission_classes = [IsAuthenticated]

    def _get_day_log(self, request, day_log_id):
        log = get_object_or_404(DayLog, pk=day_log_id)
        if not _is_manager(request.user) and log.user != request.user:
            return None, Response({'detail': 'Not found.'}, status=404)
        return log, None

    def get(self, request, day_log_id):
        log, err = self._get_day_log(request, day_log_id)
        if err:
            return err
        acts = log.act_logs.all()
        return Response(ActLogSerializer(acts, many=True).data)

    def post(self, request, day_log_id):
        log, err = self._get_day_log(request, day_log_id)
        if err:
            return err

        data = request.data.copy()
        data['day_log'] = log.pk

        serializer = ActLogSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        try:
            act = serializer.save()
        except (TimeRangeOverlapError, InvalidTimeRangeError) as exc:
            return Response({'detail': exc.detail, 'code': exc.default_code}, status=exc.status_code)

        return Response(ActLogSerializer(act).data, status=status.HTTP_201_CREATED)


class ActLogDetailView(APIView):
    """
    GET    /acts/<pk>/   → retrieve
    PATCH  /acts/<pk>/   → partial update
    DELETE /acts/<pk>/   → delete
    """

    permission_classes = [IsAuthenticated]

    def _get_act(self, request, pk):
        act = get_object_or_404(ActLog.objects.select_related('day_log__user'), pk=pk)
        if not _is_manager(request.user) and act.day_log.user != request.user:
            return None, Response({'detail': 'Not found.'}, status=404)
        return act, None

    def get(self, request, pk):
        act, err = self._get_act(request, pk)
        if err:
            return err
        return Response(ActLogSerializer(act).data)

    def patch(self, request, pk):
        act, err = self._get_act(request, pk)
        if err:
            return err

        serializer = ActLogSerializer(act, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            updated = serializer.save()
        except (TimeRangeOverlapError, InvalidTimeRangeError) as exc:
            return Response({'detail': exc.detail, 'code': exc.default_code}, status=exc.status_code)

        return Response(ActLogSerializer(updated).data)

    def delete(self, request, pk):
        act, err = self._get_act(request, pk)
        if err:
            return err
        act.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Driver overview
# ---------------------------------------------------------------------------

class DriverOverviewView(APIView):
    """
    GET /managers/drivers/
        Returns all drivers (with co-driver info) and summary counts.
        Managers only.

    GET /managers/drivers/<driver_id>/logs/
        All logs for a specific driver with full period filtering.
        Same query params as DayLogListView.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, driver_id=None):
        if not _is_manager(request.user):
            return Response({'detail': 'Managers only.'}, status=403)

        from authApi.models import User

        if driver_id:
            driver = get_object_or_404(User, pk=driver_id, is_driver=True)
            qs = DayLog.objects.filter(user=driver).select_related('user', 'co_driver')

            # Reuse the same period / date filters
            today = datetime.date.today()
            period = request.query_params.get('period')

            if period == 'today':
                qs = qs.filter(day=today)
            elif period == 'this_week':
                start = today - datetime.timedelta(days=today.weekday())
                qs = qs.filter(day__gte=start, day__lte=today)
            elif period == 'this_month':
                qs = qs.filter(day__year=today.year, day__month=today.month)
            elif period == 'this_year':
                qs = qs.filter(day__year=today.year)
            else:
                date_str = request.query_params.get('date')
                week_str = request.query_params.get('week')
                month_str = request.query_params.get('month')
                year_str = request.query_params.get('year')

                if date_str:
                    parsed = parse_date(date_str)
                    if parsed:
                        qs = qs.filter(day=parsed)
                elif week_str:
                    try:
                        year = int(year_str or today.year)
                        week = int(week_str)
                        week_start = datetime.date.fromisocalendar(year, week, 1)
                        qs = qs.filter(day__gte=week_start, day__lte=week_start + datetime.timedelta(days=6))
                    except (ValueError, TypeError):
                        pass
                elif month_str:
                    try:
                        qs = qs.filter(day__year=int(year_str or today.year), day__month=int(month_str))
                    except (ValueError, TypeError):
                        pass
                elif year_str:
                    try:
                        qs = qs.filter(day__year=int(year_str))
                    except (ValueError, TypeError):
                        pass

            return Response(DayLogListSerializer(qs.order_by('day'), many=True).data)

        # No driver_id → list all drivers
        drivers = User.objects.filter(is_driver=True).order_by('last_name', 'first_name')
        data = []
        for driver in drivers:
            log_count = DayLog.objects.filter(user=driver).count()
            data.append({
                'id': driver.pk,
                'email': driver.email,
                'name': f"{driver.first_name} {driver.last_name}".strip() or driver.email,
                'designation_number': driver.designation_number,
                'total_logs': log_count,
            })
        return Response(data)
    

class DriverSearchView(APIView):
    """
    GET /drivers/search/?q=<query>
    Returns drivers matching the query against name, email, or
    designation number. Accessible by any authenticated user
    (drivers need this to find the main driver when submitting
    as co-driver).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from authApi.models import User
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response([])

        drivers = User.objects.filter(
            is_driver=True
        ).filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)  |
            Q(email__icontains=q)      |
            Q(designation_number__icontains=q)
        ).order_by('last_name', 'first_name')[:20]

        data = [
            {
                'id': d.pk,
                'email': d.email,
                'name': f"{d.first_name} {d.last_name}".strip() or d.email,
                'designation_number': d.designation_number,
            }
            for d in drivers
        ]
        return Response(data)


class DriverPublicLogsView(APIView):
    """
    GET /drivers/<driver_id>/logs/?period=this_month
    Returns a slim log list for a specific driver.
    Accessible by any authenticated driver — used by the
    co-driver submission flow to find the main driver's log.
    Only exposes: id, day, from_location, to_location.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, driver_id):
        from authApi.models import User
        driver = get_object_or_404(User, pk=driver_id, is_driver=True)

        qs = DayLog.objects.filter(user=driver).order_by('-day')

        today = datetime.date.today()
        period = request.query_params.get('period', 'this_month')

        if period == 'today':
            qs = qs.filter(day=today)
        elif period == 'this_week':
            start = today - datetime.timedelta(days=today.weekday())
            qs = qs.filter(day__gte=start, day__lte=today)
        elif period == 'this_month':
            qs = qs.filter(day__year=today.year, day__month=today.month)
        elif period == 'this_year':
            qs = qs.filter(day__year=today.year)

        data = [
            {
                'id': log.pk,
                'day': str(log.day),
                'from_location': log.from_location,
                'to_location': log.to_location,
            }
            for log in qs[:60]  # cap at 60 entries
        ]
        return Response(data)