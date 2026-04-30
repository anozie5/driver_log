from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from tripApi.models import Trip
from tripApi.serializers import TripCreateSerializer, TripDetailSerializer, TripListSerializer
from tripApi.planner import execute_trip_plan


def _is_manager(user):
    return user.is_manager


class TripListView(APIView):
    """
    GET  /trips/   — list trips for the current driver
                     managers see all trips (filter: ?driver_id=<pk>)
    POST /trips/   — create + immediately plan a trip
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if _is_manager(request.user):
            qs = Trip.objects.select_related('driver').all()
            driver_id = request.query_params.get('driver_id')
            if driver_id:
                qs = qs.filter(driver_id=driver_id)
        else:
            if not request.user.is_driver:
                return Response({'detail': 'Drivers only.'}, status=403)
            qs = Trip.objects.filter(driver=request.user)

        return Response(TripListSerializer(qs, many=True).data)

    def post(self, request):
        if not request.user.is_driver:
            return Response({'detail': 'Only drivers can plan trips.'}, status=403)

        serializer = TripCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # Default departure_time to now if not supplied
        if 'departure_time' not in serializer.validated_data:
            serializer.validated_data['departure_time'] = timezone.now()

        trip = serializer.save()

        # Plan synchronously — fast enough for typical trips (see hos.py notes)
        try:
            trip = execute_trip_plan(trip.pk)
        except Exception as exc:
            # Trip saved with status='failed'; return 422 with the error
            return Response(
                {
                    'detail': 'Trip planning failed.',
                    'error': str(exc),
                    'trip_id': trip.pk,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            TripDetailSerializer(trip, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class TripDetailView(APIView):
    """
    GET    /trips/<pk>/       — full trip detail (stops + ELD logs)
    DELETE /trips/<pk>/       — delete trip + linked stops (does NOT delete DayLogs)
    POST   /trips/<pk>/replan — re-run the planner (e.g. after input correction)
    """
    permission_classes = [IsAuthenticated]

    def _get_trip(self, request, pk):
        trip = get_object_or_404(Trip.objects.select_related('driver'), pk=pk)
        if not _is_manager(request.user) and trip.driver != request.user:
            return None, Response({'detail': 'Not found.'}, status=404)
        return trip, None

    def get(self, request, pk):
        trip, err = self._get_trip(request, pk)
        if err:
            return err
        return Response(TripDetailSerializer(trip, context={'request': request}).data)

    def delete(self, request, pk):
        trip, err = self._get_trip(request, pk)
        if err:
            return err
        trip.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def post(self, request, pk):
        """POST /trips/<pk>/replan — re-run planner for an existing trip."""
        trip, err = self._get_trip(request, pk)
        if err:
            return err

        try:
            trip = execute_trip_plan(trip.pk)
        except Exception as exc:
            return Response(
                {'detail': 'Replanning failed.', 'error': str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(TripDetailSerializer(trip, context={'request': request}).data)