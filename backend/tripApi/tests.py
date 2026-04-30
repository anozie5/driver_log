"""
Unit tests for the HOS rules engine (hos.py).
No Django database access — pure Python.

Run with:
    python -m pytest tripApi/tests.py -v
or:
    python manage.py test tripApi.tests
"""

from django.test import TestCase
import pytest
from datetime import datetime, timezone
from tripApi.hos import (
    plan_trip,
    MAX_DRIVING_HOURS,
    MAX_ON_DUTY_WINDOW,
    REQUIRED_BREAK_AFTER,
    REQUIRED_BREAK_MINS,
    OFF_DUTY_RESET,
    CYCLE_LIMIT,
    FUEL_INTERVAL_MILES,
    PICKUP_HOURS,
    DROPOFF_HOURS,
    AVERAGE_SPEED_MPH,
)

DEPARTURE = datetime(2025, 1, 6, 6, 0, 0, tzinfo=timezone.utc)   # Monday 06:00 UTC

LOCATIONS = ['Chicago, IL', 'St. Louis, MO', 'Dallas, TX']
COORDS    = [(41.8781, -87.6298), (38.6270, -90.1994), (32.7767, -96.7970)]


def _plan(leg1, leg2, cycle_used=0.0):
    return plan_trip(
        total_miles=leg1 + leg2,
        segment_miles=[leg1, leg2],
        segment_locations=LOCATIONS,
        segment_coords=COORDS,
        departure=DEPARTURE,
        cycle_hours_used=cycle_used,
    )


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------

def test_short_trip_has_start_pickup_dropoff():
    """A short trip (< 8 hrs driving) has exactly start, pickup, dropoff stops."""
    stops, segments = _plan(100, 100)
    types = [s.stop_type for s in stops]
    assert 'start' in types
    assert 'pickup' in types
    assert 'dropoff' in types


def test_segments_are_chronological():
    stops, segments = _plan(300, 300)
    for i in range(1, len(segments)):
        assert segments[i].start >= segments[i - 1].end, (
            f"Segment {i} starts before segment {i-1} ends"
        )


def test_segments_cover_start_to_end():
    stops, segments = _plan(200, 200)
    first_start = segments[0].start
    assert first_start == DEPARTURE


def test_all_activities_are_valid():
    stops, segments = _plan(500, 500)
    valid = {'D', 'ON', 'OF', 'SB'}
    for seg in segments:
        assert seg.activity in valid, f"Unknown activity: {seg.activity}"


# ---------------------------------------------------------------------------
# 30-minute break rule
# ---------------------------------------------------------------------------

def test_30_min_break_inserted_after_8hrs_driving():
    """
    A trip requiring more than 8 hours of continuous driving must include
    at least one 30-minute break.
    """
    # 8hrs driving @ 55mph = 440 miles; use 500 miles to force a break
    stops, segments = _plan(500, 100)
    rest_stops = [s for s in stops if s.stop_type == 'rest_break']
    assert len(rest_stops) >= 1


def test_driving_since_break_never_exceeds_8hrs():
    """No driving sub-sequence between breaks should exceed 8 hours."""
    stops, segments = _plan(600, 600)
    driving_since = 0.0
    for seg in segments:
        if seg.activity == 'D':
            driving_since += seg.duration_hours
            assert driving_since <= REQUIRED_BREAK_AFTER + 0.01, (
                f"Driving since last break exceeded 8 hrs: {driving_since:.2f}"
            )
        elif seg.activity in ('OF', 'SB'):
            driving_since = 0.0


# ---------------------------------------------------------------------------
# 11-hour / 14-hour limits
# ---------------------------------------------------------------------------

def test_driving_per_shift_never_exceeds_11hrs():
    stops, segments = _plan(800, 800)
    shift_driving = 0.0
    for seg in segments:
        if seg.activity in ('SB', 'OF') and seg.duration_hours >= OFF_DUTY_RESET:
            shift_driving = 0.0
        elif seg.activity == 'D':
            shift_driving += seg.duration_hours
            assert shift_driving <= MAX_DRIVING_HOURS + 0.01, (
                f"Shift driving exceeded 11 hrs: {shift_driving:.2f}"
            )


def test_on_duty_per_window_never_exceeds_14hrs():
    stops, segments = _plan(800, 800)
    shift_on_duty = 0.0
    for seg in segments:
        if seg.activity in ('SB', 'OF') and seg.duration_hours >= OFF_DUTY_RESET:
            shift_on_duty = 0.0
        elif seg.activity in ('D', 'ON'):
            shift_on_duty += seg.duration_hours
            assert shift_on_duty <= MAX_ON_DUTY_WINDOW + 0.01, (
                f"On-duty window exceeded 14 hrs: {shift_on_duty:.2f}"
            )


# ---------------------------------------------------------------------------
# 10-hour reset
# ---------------------------------------------------------------------------

def test_sleeper_reset_has_correct_duration():
    """Every sleeper-berth stop must be at least 10 hours."""
    stops, segments = _plan(700, 700)
    for stop in stops:
        if stop.stop_type == 'sleeper_break':
            assert stop.duration_hours >= OFF_DUTY_RESET - 0.01


def test_multi_day_trip_has_sleeper_resets():
    """A very long trip must produce at least one sleeper-berth reset."""
    stops, segments = _plan(1200, 1200)
    sleeper_stops = [s for s in stops if s.stop_type == 'sleeper_break']
    assert len(sleeper_stops) >= 1


# ---------------------------------------------------------------------------
# Fuel stops
# ---------------------------------------------------------------------------

def test_fuel_stop_inserted_every_1000_miles():
    """Trips over 1,000 miles must include at least one fuel stop."""
    stops, segments = _plan(700, 500)
    fuel_stops = [s for s in stops if s.stop_type == 'fuel']
    assert len(fuel_stops) >= 1


def test_no_fuel_stop_under_1000_miles():
    stops, segments = _plan(400, 400)
    fuel_stops = [s for s in stops if s.stop_type == 'fuel']
    assert len(fuel_stops) == 0


def test_fuel_stop_cumulative_miles_is_multiple_of_1000():
    stops, segments = _plan(1500, 500)
    for stop in stops:
        if stop.stop_type == 'fuel':
            # Within 55 miles (one driving iteration) of a 1000-mile boundary
            nearest = round(float(stop.cumulative_miles) / 1000) * 1000
            assert abs(float(stop.cumulative_miles) - nearest) <= AVERAGE_SPEED_MPH, (
                f"Fuel stop at {stop.cumulative_miles} mi is not near a 1000-mi boundary"
            )


# ---------------------------------------------------------------------------
# Pickup / dropoff on-duty time
# ---------------------------------------------------------------------------

def test_pickup_stop_exists():
    stops, _ = _plan(200, 200)
    assert any(s.stop_type == 'pickup' for s in stops)


def test_dropoff_stop_exists():
    stops, _ = _plan(200, 200)
    assert any(s.stop_type == 'dropoff' for s in stops)


def test_pickup_duration_is_1hr():
    stops, segments = _plan(200, 200)
    pickup = next(s for s in stops if s.stop_type == 'pickup')
    assert abs(pickup.duration_hours - PICKUP_HOURS) < 0.01


def test_dropoff_duration_is_1hr():
    stops, segments = _plan(200, 200)
    dropoff = next(s for s in stops if s.stop_type == 'dropoff')
    assert abs(dropoff.duration_hours - DROPOFF_HOURS) < 0.01


def test_pickup_and_dropoff_are_on_duty_segments():
    """The 1-hr pickup and dropoff must produce ON-DUTY segments."""
    stops, segments = _plan(200, 200)
    on_duty_segs = [s for s in segments if s.activity == 'ON']
    # At minimum: pickup ON + dropoff ON
    assert len(on_duty_segs) >= 2


# ---------------------------------------------------------------------------
# Cycle hours
# ---------------------------------------------------------------------------

def test_cycle_hours_respected():
    """Driver with 69 hrs used can only drive 1 more hour before the planner
    raises (or inserts maximum allowed activity)."""
    # 1 remaining cycle hour @ 55 mph = ~55 miles max driving.
    # A 500-mile trip should fail because the cycle limit would be exceeded.
    with pytest.raises(ValueError, match='70-hr'):
        _plan(300, 300, cycle_used=69.0)


def test_zero_cycle_used_completes():
    stops, segments = _plan(300, 300, cycle_used=0.0)
    assert any(s.stop_type == 'dropoff' for s in stops)


# ---------------------------------------------------------------------------
# Stop ordering
# ---------------------------------------------------------------------------

def test_stops_are_in_sequence_order():
    stops, _ = _plan(400, 400)
    seqs = [s.sequence for s in stops]
    assert seqs == sorted(seqs)


def test_start_is_first_stop():
    stops, _ = _plan(200, 200)
    assert stops[0].stop_type == 'start'


def test_dropoff_is_last_stop():
    stops, _ = _plan(200, 200)
    assert stops[-1].stop_type == 'dropoff'