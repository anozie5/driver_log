"""
Orchestrates the full trip planning pipeline:

  1. Geocode the three locations (current, pickup, dropoff)
  2. Fetch driving distance/route from OpenRouteService (free, no key billing)
  3. Run the HOS engine (hos.py) to produce stops + activity segments
  4. Persist everything: Trip, TripStop, DayLog, ActLog, TripDayLog

Called from the API view — always runs synchronously (cheap enough, see
earlier discussion on signals vs async tasks).

Map API used: OpenRouteService (ORS)
  - Free tier: 2,000 req/day, no credit card required
  - Docs: https://openrouteservice.org/dev/#/api-docs
  - Set ORS_API_KEY in Django settings / environment variables.
"""

import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone as dj_timezone

from tripApi.models import Trip, TripStop, TripDayLog
from tripApi.hos import plan_trip, Segment, AVERAGE_SPEED_MPH
from logApi.models import DayLog, ActLog
from authApi.models import User

logger = logging.getLogger(__name__)

ORS_BASE = 'https://api.openrouteservice.org'


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def geocode(address: str) -> tuple:
    """
    Return (lat, lon) for a free-text address using ORS geocoding.
    Raises RuntimeError if the address cannot be resolved.
    """
    api_key = getattr(settings, 'ORS_API_KEY', '')
    if not api_key:
        raise RuntimeError('ORS_API_KEY is not configured in settings.')

    resp = requests.get(
        f'{ORS_BASE}/geocode/search',
        params={'api_key': api_key, 'text': address, 'size': 1},
        timeout=10,
    )
    resp.raise_for_status()
    features = resp.json().get('features', [])
    if not features:
        raise RuntimeError(f'Could not geocode address: "{address}"')

    lon, lat = features[0]['geometry']['coordinates']
    return float(lat), float(lon)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def get_route(coords: list) -> dict:
    """
    Fetch a driving route between an ordered list of (lat, lon) tuples.
    Returns the ORS directions response dict.

    coords example: [(lat1, lon1), (lat2, lon2), (lat3, lon3)]
    ORS expects [lon, lat] order in the request body.
    """
    api_key = getattr(settings, 'ORS_API_KEY', '')
    resp = requests.post(
        f'{ORS_BASE}/v2/directions/driving-hgv/geojson',
        headers={'Authorization': api_key, 'Content-Type': 'application/json'},
        json={
            'coordinates': [[lon, lat] for lat, lon in coords],
            'instructions': False,
            'geometry': True,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def extract_leg_distances(route_json: dict) -> tuple:
    """
    Pull per-segment distances (in miles) and total distance from an ORS
    GeoJSON directions response.

    Returns (leg_miles_list, total_miles, geojson_feature)
    """
    features = route_json.get('features', [])
    if not features:
        raise RuntimeError('ORS returned no route features.')

    feature = features[0]
    props = feature['properties']
    segments = props.get('segments', [])

    # ORS returns distances in metres
    M_TO_MILES = 0.000621371
    leg_miles = [seg['distance'] * M_TO_MILES for seg in segments]
    total_miles = props['summary']['distance'] * M_TO_MILES

    return leg_miles, total_miles, feature


# ---------------------------------------------------------------------------
# ELD log builder
# ---------------------------------------------------------------------------

def _round_to_quarter(dt: datetime) -> datetime:
    """Snap a datetime to the nearest 15-minute boundary (floor)."""
    minute = (dt.minute // 15) * 15
    return dt.replace(minute=minute, second=0, microsecond=0)


def _build_eld_logs(
    driver: User,
    segments: list,
    trip: Trip,
    from_location: str,
    to_location: str,
) -> list:
    """
    Group Segments by calendar day, create one DayLog per day,
    and create ActLog rows for each segment within that day.

    Returns a list of (DayLog, day_number) tuples.
    """

    # Group segments by date in the driver's local day
    # (using UTC date — adjust if you add timezone support)
    by_day = defaultdict(list)
    for seg in segments:
        day_key = seg.start.date()
        by_day[day_key].append(seg)

    results = []
    for day_number, (day_date, day_segs) in enumerate(sorted(by_day.items()), start=1):

        day_log, _ = DayLog.objects.get_or_create(
            user=driver,
            day=day_date,
            defaults={
                'from_location': from_location,
                'to_location': to_location,
                'carrier_name': getattr(driver, 'carrier_name', ''),
            },
        )

        for seg in day_segs:
            start = _round_to_quarter(seg.start)
            end   = _round_to_quarter(seg.end)

            # Clamp to the same calendar day — segments crossing midnight
            # are cut at 23:45 and the remainder opens the next day's log
            # (the planner already splits them, but guard anyway).
            day_end = start.replace(hour=23, minute=45, second=0, microsecond=0)
            if end > day_end + timedelta(minutes=15):
                end = day_end + timedelta(minutes=15)

            if start >= end:
                continue    # negligible rounding artifact — skip

            # Avoid creating duplicate or overlapping ActLogs if
            # re-planning an existing trip.
            overlapping = ActLog.objects.filter(
                day_log=day_log,
                start_time__lt=end,
                end_time__gt=start,
            ).exists()
            if overlapping:
                continue

            ActLog.objects.create(
                day_log=day_log,
                activity=seg.activity,
                start_time=start,
                end_time=end,
                location=seg.location[:255] if seg.location else '',
                remarks=seg.notes[:500] if seg.notes else '',
            )

        results.append((day_log, day_number))

    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

@transaction.atomic
def execute_trip_plan(trip_id: int) -> Trip:
    """
    Run the full planning pipeline for an existing Trip record.

    1. Geocode locations
    2. Fetch ORS route
    3. Run HOS engine
    4. Persist TripStop, DayLog, ActLog, TripDayLog rows
    5. Update Trip.status to 'computed'

    Raises on any error; the atomic transaction rolls back everything.
    """
    trip = Trip.objects.select_related('driver').get(pk=trip_id)
    trip.status = Trip.StatusChoices.PENDING
    trip.save(update_fields=['status'])

    try:
        # -- 1. Geocode --
        logger.info('Geocoding locations for trip #%s', trip_id)
        current_coord = geocode(trip.current_location)
        pickup_coord  = geocode(trip.pickup_location)
        dropoff_coord = geocode(trip.dropoff_location)

        # -- 2. Route --
        logger.info('Fetching route for trip #%s', trip_id)
        route_json = get_route([current_coord, pickup_coord, dropoff_coord])
        leg_miles, total_miles, route_feature = extract_leg_distances(route_json)

        # ORS may return 2 legs (current→pickup, pickup→dropoff)
        if len(leg_miles) < 2:
            raise RuntimeError('Expected 2 route legs; ORS returned fewer.')

        leg1_miles, leg2_miles = leg_miles[0], leg_miles[1]
        total_driving_hours = total_miles / AVERAGE_SPEED_MPH

        # -- 3. HOS engine --
        logger.info('Running HOS engine for trip #%s (%.1f miles)', trip_id, total_miles)
        stops, segments = plan_trip(
            total_miles=total_miles,
            segment_miles=[leg1_miles, leg2_miles],
            segment_locations=[
                trip.current_location,
                trip.pickup_location,
                trip.dropoff_location,
            ],
            segment_coords=[current_coord, pickup_coord, dropoff_coord],
            departure=trip.departure_time,
            cycle_hours_used=float(trip.current_cycle_used),
        )

        # -- 4a. Persist TripStops --
        logger.info('Saving %d stops for trip #%s', len(stops), trip_id)
        TripStop.objects.filter(trip=trip).delete()   # clear any prior plan

        # Enrich fuel/rest stops with interpolated coordinates
        stop_objs = []
        for ps in stops:
            # Assign coordinates from known waypoints; interpolated stops get None
            stop_objs.append(TripStop(
                trip=trip,
                sequence=ps.sequence,
                stop_type=ps.stop_type,
                location=ps.location,
                latitude=ps.latitude,
                longitude=ps.longitude,
                miles_from_prev=ps.miles_from_prev,
                cumulative_miles=ps.cumulative_miles,
                arrival_time=ps.arrival,
                departure_time=ps.departure,
                duration_hours=ps.duration_hours,
                notes=ps.notes,
            ))
        TripStop.objects.bulk_create(stop_objs)

        # -- 4b. Build ELD logs --
        logger.info('Building ELD logs for trip #%s', trip_id)
        TripDayLog.objects.filter(trip=trip).delete()  # clear prior logs

        eld_results = _build_eld_logs(
            driver=trip.driver,
            segments=segments,
            trip=trip,
            from_location=trip.current_location,
            to_location=trip.dropoff_location,
        )

        trip_day_log_objs = [
            TripDayLog(trip=trip, day_log=dl, day_number=dn)
            for dl, dn in eld_results
        ]
        TripDayLog.objects.bulk_create(trip_day_log_objs)

        # -- 5. Update Trip record --
        trip.status = Trip.StatusChoices.COMPUTED
        trip.route_geojson = route_feature
        trip.total_distance_miles = round(total_miles, 2)
        trip.total_driving_hours  = round(total_driving_hours, 2)
        trip.save(update_fields=[
            'status', 'route_geojson',
            'total_distance_miles', 'total_driving_hours',
            'updated_at',
        ])

        logger.info(
            'Trip #%s planned: %.1f miles, %d days, %d stops',
            trip_id, total_miles, len(eld_results), len(stops),
        )

    except Exception as exc:
        trip.status = Trip.StatusChoices.FAILED
        trip.error_message = str(exc)
        trip.save(update_fields=['status', 'error_message', 'updated_at'])
        logger.exception('Trip planning failed for trip #%s', trip_id)
        raise

    return trip