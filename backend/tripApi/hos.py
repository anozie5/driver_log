"""
Hours-of-Service (HOS) rules engine.

Implements the FMCSA property-carrying driver rules used in this project:
  - 11-hour driving limit per shift
  - 14-hour on-duty window per shift
  - 30-minute break required after 8 cumulative driving hours
  - 10-hour off-duty (sleeper berth) reset between shifts
  - 70-hour / 8-day cycle limit
  - No adverse driving condition exception (per assessment assumptions)
  - Fueling stop every ≤ 1,000 miles (per assessment assumptions)
  - 1 hour for pickup, 1 hour for dropoff (per assessment assumptions)

All time values are in decimal hours unless stated otherwise.
This module is pure Python with no Django or database imports — it can be
unit-tested in isolation and called from the planner.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional


# ---------------------------------------------------------------------------
# FMCSA constants
# ---------------------------------------------------------------------------

MAX_DRIVING_HOURS     = 11.0   # max driving in one shift
MAX_ON_DUTY_WINDOW    = 14.0   # max on-duty window before mandatory 10hr rest
REQUIRED_BREAK_AFTER  = 8.0    # driving hours before mandatory 30-min break
REQUIRED_BREAK_MINS   = 0.5    # 30 minutes expressed as hours
OFF_DUTY_RESET        = 10.0   # hours of off-duty/sleeper to reset shift limits
CYCLE_LIMIT           = 70.0   # 70hr / 8-day cycle
FUEL_INTERVAL_MILES   = 1000.0 # max miles between fueling stops
PICKUP_HOURS          = 1.0    # on-duty time for pickup
DROPOFF_HOURS         = 1.0    # on-duty time for dropoff
AVERAGE_SPEED_MPH     = 55.0   # assumed average driving speed


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    """One planned activity segment that will become an ActLog row."""

    # Maps to ActLog.ActivityType values
    activity: str           # 'D' | 'ON' | 'OF' | 'SB'
    start: datetime
    end: datetime
    location: str
    notes: str = ''

    @property
    def duration_hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600


@dataclass
class PlannedStop:
    """A waypoint produced by the planner — later saved as TripStop."""
    sequence: int
    stop_type: str          # TripStop.StopType values
    location: str
    latitude: Optional[float]
    longitude: Optional[float]
    miles_from_prev: float
    cumulative_miles: float
    arrival: datetime
    departure: datetime
    duration_hours: float
    notes: str = ''


@dataclass
class HOSState:
    """
    Mutable HOS state carried forward as the planner walks the route.

    driving_since_break  — driving hours accumulated since last 30-min break
    shift_driving        — driving hours in the current 14-hr window
    shift_on_duty        — on-duty hours in the current 14-hr window
    shift_start          — wall-clock start of the current 14-hr window
    cycle_hours_used     — total on-duty hours in the rolling 8-day cycle
    """
    driving_since_break: float = 0.0
    shift_driving: float = 0.0
    shift_on_duty: float = 0.0
    shift_start: Optional[datetime] = None
    cycle_hours_used: float = 0.0

    def reset_shift(self, now: datetime) -> None:
        """Called after a 10-hour off-duty / sleeper-berth reset."""
        self.driving_since_break = 0.0
        self.shift_driving = 0.0
        self.shift_on_duty = 0.0
        self.shift_start = now

    def remaining_drive_hours(self) -> float:
        """Hours of driving still allowed before any limit is hit."""
        limits = [
            MAX_DRIVING_HOURS - self.shift_driving,
            REQUIRED_BREAK_AFTER - self.driving_since_break,
            CYCLE_LIMIT - self.cycle_hours_used,
        ]
        if self.shift_start:
            elapsed = 0.0   # computed by caller when needed
        return max(0.0, min(limits))

    def remaining_window_hours(self) -> float:
        """Hours remaining in the 14-hr on-duty window."""
        return max(0.0, MAX_ON_DUTY_WINDOW - self.shift_on_duty)


# ---------------------------------------------------------------------------
# Core planner
# ---------------------------------------------------------------------------

def plan_trip(
    *,
    total_miles: float,
    segment_miles: List[float],          # miles per leg: [to_pickup, pickup_to_dropoff]
    segment_locations: List[str],        # [current, pickup, dropoff]
    segment_coords: List[tuple],         # [(lat,lon), (lat,lon), (lat,lon)]
    departure: datetime,
    cycle_hours_used: float,
) -> tuple:
    """
    Build the full sequence of PlannedStops and activity Segments for a trip.

    Parameters
    ----------
    total_miles          : total driving distance (current → pickup → dropoff)
    segment_miles        : [miles current→pickup, miles pickup→dropoff]
    segment_locations    : [current_location, pickup_location, dropoff_location]
    segment_coords       : [(lat,lon) for each location above]
    departure            : datetime the driver leaves current_location
    cycle_hours_used     : hours already used in the 70hr/8-day cycle

    Returns
    -------
    (stops: List[PlannedStop], segments: List[Segment])
    """

    hos = HOSState(
        cycle_hours_used=float(cycle_hours_used),
        shift_start=departure,
    )

    stops: List[PlannedStop] = []
    segments: List[Segment] = []
    clock = departure        # current wall-clock position
    cum_miles = 0.0
    seq = 0

    # -----------------------------------------------------------------------
    # Helper: add a driving block of `drive_hours` hours
    # -----------------------------------------------------------------------
    def _drive(hours: float, miles: float, from_loc: str, to_loc: str,
               from_coord, to_coord):
        nonlocal clock, cum_miles, seq
        start = clock
        end = clock + timedelta(hours=hours)
        segments.append(Segment(
            activity='D',
            start=start,
            end=end,
            location=from_loc,
            notes=f'Driving toward {to_loc}',
        ))
        hos.shift_driving += hours
        hos.shift_on_duty += hours
        hos.driving_since_break += hours
        hos.cycle_hours_used += hours
        clock = end
        cum_miles += miles

    # -----------------------------------------------------------------------
    # Helper: add an on-duty (not driving) block
    # -----------------------------------------------------------------------
    def _on_duty(hours: float, location: str, note: str):
        nonlocal clock
        start = clock
        end = clock + timedelta(hours=hours)
        segments.append(Segment(activity='ON', start=start, end=end,
                                location=location, notes=note))
        hos.shift_on_duty += hours
        hos.cycle_hours_used += hours
        clock = end

    # -----------------------------------------------------------------------
    # Helper: add a rest break (30 min off-duty)
    # -----------------------------------------------------------------------
    def _rest_break(location: str):
        nonlocal clock, seq
        arr = clock
        dep = clock + timedelta(hours=REQUIRED_BREAK_MINS)
        segments.append(Segment(activity='OF', start=arr, end=dep,
                                location=location, notes='30-min mandatory rest break'))
        stops.append(PlannedStop(
            sequence=seq, stop_type='rest_break', location=location,
            latitude=None, longitude=None,
            miles_from_prev=0, cumulative_miles=cum_miles,
            arrival=arr, departure=dep,
            duration_hours=REQUIRED_BREAK_MINS,
            notes='30-min mandatory rest break (8hr driving limit)',
        ))
        seq += 1
        hos.driving_since_break = 0.0
        clock = dep

    # -----------------------------------------------------------------------
    # Helper: add a 10-hour sleeper / off-duty reset
    # -----------------------------------------------------------------------
    def _sleeper_reset(location: str, coord):
        nonlocal clock, seq
        arr = clock
        dep = clock + timedelta(hours=OFF_DUTY_RESET)
        segments.append(Segment(activity='SB', start=arr, end=dep,
                                location=location,
                                notes='10-hr sleeper berth reset'))
        stops.append(PlannedStop(
            sequence=seq, stop_type='sleeper_break', location=location,
            latitude=coord[0] if coord else None,
            longitude=coord[1] if coord else None,
            miles_from_prev=0, cumulative_miles=cum_miles,
            arrival=arr, departure=dep,
            duration_hours=OFF_DUTY_RESET,
            notes='10-hr sleeper berth (shift reset)',
        ))
        seq += 1
        clock = dep
        hos.reset_shift(clock)

    # -----------------------------------------------------------------------
    # Helper: drive a sub-leg respecting all HOS limits, inserting breaks,
    # sleeper resets, and fuel stops as needed.
    # -----------------------------------------------------------------------
    def _drive_leg(leg_miles: float, from_loc: str, to_loc: str,
                   from_coord, to_coord):
        nonlocal clock, cum_miles, seq

        miles_left = leg_miles
        prev_miles = cum_miles

        while miles_left > 0:

            # 1. Check cycle — if at limit, driver cannot continue.
            if hos.cycle_hours_used >= CYCLE_LIMIT:
                raise ValueError(
                    f'Driver has exhausted the 70-hr/8-day cycle '
                    f'({hos.cycle_hours_used:.1f} hrs used). Trip cannot be completed.'
                )

            # 2. If 14-hr window is exhausted, take a 10-hr reset.
            if hos.shift_on_duty >= MAX_ON_DUTY_WINDOW:
                _sleeper_reset(from_loc, from_coord)

            # 3. If 11-hr driving limit is hit, take a 10-hr reset.
            if hos.shift_driving >= MAX_DRIVING_HOURS:
                _sleeper_reset(from_loc, from_coord)

            # 4. If 8-hr break threshold reached, take a 30-min break.
            if hos.driving_since_break >= REQUIRED_BREAK_AFTER:
                _rest_break(from_loc)

            # 5. How many hours can we drive right now?
            max_drive_now = min(
                MAX_DRIVING_HOURS   - hos.shift_driving,           # 11-hr limit
                REQUIRED_BREAK_AFTER - hos.driving_since_break,    # 8-hr break threshold
                MAX_ON_DUTY_WINDOW  - hos.shift_on_duty,            # 14-hr window
                CYCLE_LIMIT         - hos.cycle_hours_used,         # 70-hr cycle
            )
            if max_drive_now <= 0:
                _sleeper_reset(from_loc, from_coord)
                continue

            # 6. How many miles can we cover in that time?
            max_miles_by_hos = max_drive_now * AVERAGE_SPEED_MPH

            # 7. Fuel stop: how far until we need to refuel?
            miles_since_fuel = cum_miles % FUEL_INTERVAL_MILES
            miles_until_fuel = FUEL_INTERVAL_MILES - miles_since_fuel
            if miles_since_fuel == 0 and cum_miles > 0:
                miles_until_fuel = FUEL_INTERVAL_MILES

            # 8. How far do we actually drive this iteration?
            drive_miles = min(miles_left, max_miles_by_hos, miles_until_fuel)
            drive_hours = drive_miles / AVERAGE_SPEED_MPH

            # Interpolate an approximate location label
            progress = (leg_miles - miles_left + drive_miles) / leg_miles
            if progress >= 0.99:
                loc_label = to_loc
            else:
                loc_label = f'En route to {to_loc} ({int(cum_miles + drive_miles)} mi)'

            _drive(drive_hours, drive_miles, from_loc, loc_label, from_coord, to_coord)
            miles_left -= drive_miles

            # 9. Fuel stop if we just hit the interval
            if cum_miles % FUEL_INTERVAL_MILES < 1.0 and cum_miles > 0:
                fuel_loc = f'Fuel stop near {loc_label}'
                fuel_arr = clock
                fuel_dep = clock + timedelta(minutes=30)
                segments.append(Segment(activity='ON', start=fuel_arr, end=fuel_dep,
                                        location=fuel_loc, notes='Fueling stop'))
                stops.append(PlannedStop(
                    sequence=seq, stop_type='fuel', location=fuel_loc,
                    latitude=None, longitude=None,
                    miles_from_prev=drive_miles,
                    cumulative_miles=cum_miles,
                    arrival=fuel_arr, departure=fuel_dep,
                    duration_hours=0.5,
                    notes='Fuel stop (≤1,000-mile interval)',
                ))
                seq += 1
                hos.shift_on_duty += 0.5
                hos.cycle_hours_used += 0.5
                clock = fuel_dep

    # -----------------------------------------------------------------------
    # Build the route
    # -----------------------------------------------------------------------
    current_loc, pickup_loc, dropoff_loc = segment_locations
    current_coord, pickup_coord, dropoff_coord = segment_coords
    leg1_miles, leg2_miles = segment_miles

    # -- Stop 0: Start --
    stops.append(PlannedStop(
        sequence=seq, stop_type='start', location=current_loc,
        latitude=current_coord[0], longitude=current_coord[1],
        miles_from_prev=0, cumulative_miles=0,
        arrival=departure, departure=departure, duration_hours=0,
    ))
    seq += 1

    # -- Leg 1: Drive to pickup --
    _drive_leg(leg1_miles, current_loc, pickup_loc, current_coord, pickup_coord)

    # -- Pickup: 1 hour on-duty --
    pickup_arr = clock
    _on_duty(PICKUP_HOURS, pickup_loc, 'Pickup — loading / paperwork')
    stops.append(PlannedStop(
        sequence=seq, stop_type='pickup', location=pickup_loc,
        latitude=pickup_coord[0], longitude=pickup_coord[1],
        miles_from_prev=leg1_miles, cumulative_miles=cum_miles,
        arrival=pickup_arr, departure=clock,
        duration_hours=PICKUP_HOURS,
        notes='1-hr pickup (loading and paperwork)',
    ))
    seq += 1

    # -- Leg 2: Drive to dropoff --
    _drive_leg(leg2_miles, pickup_loc, dropoff_loc, pickup_coord, dropoff_coord)

    # -- Dropoff: 1 hour on-duty --
    dropoff_arr = clock
    _on_duty(DROPOFF_HOURS, dropoff_loc, 'Dropoff — unloading / paperwork')
    stops.append(PlannedStop(
        sequence=seq, stop_type='dropoff', location=dropoff_loc,
        latitude=dropoff_coord[0], longitude=dropoff_coord[1],
        miles_from_prev=leg2_miles, cumulative_miles=cum_miles,
        arrival=dropoff_arr, departure=clock,
        duration_hours=DROPOFF_HOURS,
        notes='1-hr dropoff (unloading and paperwork)',
    ))
    seq += 1

    # -- Fill remaining day with Off Duty until midnight (or next whole hour) --
    # So the last day's log closes cleanly.
    day_end = clock.replace(hour=23, minute=59, second=0, microsecond=0)
    if clock < day_end:
        segments.append(Segment(
            activity='OF',
            start=clock,
            end=day_end + timedelta(minutes=1),
            location=dropoff_loc,
            notes='Off duty after delivery',
        ))

    return stops, segments