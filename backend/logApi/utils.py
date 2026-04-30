from decimal import Decimal

from django.db import IntegrityError, transaction

from django.core.exceptions import ValidationError as DjangoValidationError

from logApi.models import DayLog, ActLog
from logApi.exceptions import TimeRangeOverlapError, InvalidTimeRangeError


VALID_MINUTES = {0, 15, 30, 45}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_15_minute_interval(dt):
    """Raise InvalidTimeRangeError if `dt` is not on a 15-minute boundary."""
    if dt.minute not in VALID_MINUTES or dt.second != 0 or dt.microsecond != 0:
        raise InvalidTimeRangeError(
            f"Time must be on a 15-minute boundary (:00, :15, :30, :45). "
            f"Got {dt.strftime('%H:%M:%S')}."
        )


def validate_act_times(start, end):
    validate_15_minute_interval(start)
    validate_15_minute_interval(end)
    if start >= end:
        raise InvalidTimeRangeError('Start time must be strictly before end time.')


# ---------------------------------------------------------------------------
# DayLog helpers
# ---------------------------------------------------------------------------

def get_or_create_day_log(user, date_obj):
    """
    Return (instance, created) for a user's DayLog on `date_obj`.
    Scoped to the specific user — never returns another driver's log.
    """
    instance, created = DayLog.objects.get_or_create(user=user, day=date_obj)
    return instance, created


# ---------------------------------------------------------------------------
# ActLog CRUD
# ---------------------------------------------------------------------------

@transaction.atomic
def create_act_log(day_log, activity, start_time, end_time, location='', remarks=''):
    """
    Create and return an ActLog after validating times and checking for overlaps.
    Raises InvalidTimeRangeError or TimeRangeOverlapError on failure.
    """
    validate_act_times(start_time, end_time)

    try:
        act = ActLog(
            day_log=day_log,
            activity=activity,
            start_time=start_time,
            end_time=end_time,
            location=location,
            remarks=remarks,
        )
        act.full_clean()   # runs overlap check inside ActLog.clean()
        act.save()
        return act
    except DjangoValidationError as exc:
        # Surface as DRF-compatible exceptions
        msgs = exc.message_dict if hasattr(exc, 'message_dict') else {'non_field_errors': exc.messages}
        if any('overlap' in str(v).lower() for v in msgs.values()):
            raise TimeRangeOverlapError()
        raise InvalidTimeRangeError(str(exc))
    except IntegrityError as exc:
        if 'actlog_start_before_end' in str(exc) or 'unique' in str(exc).lower():
            raise InvalidTimeRangeError('Duplicate or invalid time range.')
        raise


@transaction.atomic
def update_act_log(act, activity=None, start_time=None, end_time=None, location=None, remarks=None):
    """
    Partially update an ActLog. Only supplied (non-None) fields are changed.
    """
    if activity is not None:
        act.activity = activity
    if start_time is not None:
        act.start_time = start_time
    if end_time is not None:
        act.end_time = end_time
    if location is not None:
        act.location = location
    if remarks is not None:
        act.remarks = remarks

    validate_act_times(act.start_time, act.end_time)

    try:
        act.full_clean()
        act.save()
        return act
    except DjangoValidationError as exc:
        msgs = exc.message_dict if hasattr(exc, 'message_dict') else {'non_field_errors': exc.messages}
        if any('overlap' in str(v).lower() for v in msgs.values()):
            raise TimeRangeOverlapError()
        raise InvalidTimeRangeError(str(exc))
    except IntegrityError:
        raise TimeRangeOverlapError()


# ---------------------------------------------------------------------------
# Co-driver workflow helpers
# ---------------------------------------------------------------------------

def submit_co_driver_link(co_driver_log, primary_log):
    """
    A co-driver submits their log for approval by the main driver.
    co_driver_log  — the co-driver's own DayLog
    primary_log    — the main driver's DayLog for the same day
    """
    if co_driver_log.day != primary_log.day:
        raise InvalidTimeRangeError('Co-driver log and primary log must be for the same day.')
    co_driver_log.is_co_driver_entry = True
    co_driver_log.linked_primary_log = primary_log
    co_driver_log.co_driver_approved = None  # reset to pending
    co_driver_log.save(update_fields=['is_co_driver_entry', 'linked_primary_log', 'co_driver_approved'])


def approve_co_driver_log(primary_log, co_driver_log, approve: bool):
    """
    The main driver approves or rejects a co-driver submission.
    If approved, the co_driver FK on primary_log is also set.
    """
    if co_driver_log.linked_primary_log_id != primary_log.pk:
        from logApi.exceptions import PermissionDeniedError
        raise PermissionDeniedError('This co-driver log is not linked to your log.')

    co_driver_log.co_driver_approved = approve
    co_driver_log.save(update_fields=['co_driver_approved'])

    if approve:
        primary_log.co_driver = co_driver_log.user
        primary_log.save(update_fields=['co_driver'])


# ---------------------------------------------------------------------------
# Totals sync
# ---------------------------------------------------------------------------

# Maps ActivityType choice values to their DayLog total_hours_* field name.
_ACTIVITY_TO_FIELD = {
    ActLog.ActivityType.DRIVING:       'total_hours_driving',
    ActLog.ActivityType.ON_DUTY:       'total_hours_on_duty',
    ActLog.ActivityType.OFF_DUTY:      'total_hours_off_duty',
    ActLog.ActivityType.SLEEPER_BERTH: 'total_hours_sleeping',
}


def recompute_day_log_totals(day_log: DayLog) -> None:
    """
    Recompute all hour-bucket totals on `day_log` from its ActLog rows
    and persist them in a single UPDATE.

    How each total is calculated
    ----------------------------
    For each ActLog belonging to this DayLog:
        duration = (end_time - start_time).total_seconds() / 3600

    The duration is added to whichever bucket matches the activity type:
        D  (Driving)            → total_hours_driving
        ON (On Duty not driving)→ total_hours_on_duty
        OF (Off Duty)           → total_hours_off_duty
        SB (Sleeper Berth)      → total_hours_sleeping

    Called automatically via Django signals (post_save / post_delete on ActLog).
    Can also be called manually for backfills:
        from logApi.utils import recompute_day_log_totals
        recompute_day_log_totals(some_day_log)
    """
    totals = {field: Decimal('0.00') for field in _ACTIVITY_TO_FIELD.values()}

    acts = ActLog.objects.filter(day_log=day_log).only(
        'activity', 'start_time', 'end_time'
    )

    for act in acts:
        field = _ACTIVITY_TO_FIELD.get(act.activity)
        if field is None:
            continue  # unknown activity type — skip silently
        seconds = (act.end_time - act.start_time).total_seconds()
        hours = Decimal(str(round(seconds / 3600, 6)))  # full precision before rounding
        totals[field] += hours

    # Round to 2 decimal places for storage
    for field in totals:
        totals[field] = totals[field].quantize(Decimal('0.01'))

    # Single-query UPDATE — does not trigger post_save on DayLog,
    # avoids re-entrancy, and skips auto_now field bumping on updated_at
    # (use .save(update_fields=[...]) if you want updated_at bumped too).
    DayLog.objects.filter(pk=day_log.pk).update(**totals)


def recompute_all_day_log_totals() -> int:
    """
    Backfill utility: recompute totals for every DayLog in the database.
    Run from a management command or the Django shell after a data migration.

    Returns the number of logs processed.

    Usage:
        from logApi.utils import recompute_all_day_log_totals
        count = recompute_all_day_log_totals()
        print(f"Recomputed {count} logs.")
    """
    logs = DayLog.objects.all()
    count = 0
    for log in logs.iterator(chunk_size=500):
        recompute_day_log_totals(log)
        count += 1
    return count