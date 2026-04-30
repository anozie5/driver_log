"""
Stores a trip planning request and its computed output:
  - the sequence of stops (route waypoints)
  - the generated DayLogs + ActLogs (ELD sheets)

The heavy computation lives in tripApi/planner.py.
"""

from django.db import models
from decimal import Decimal
from authApi.models import User


# Create your models here.
class Trip(models.Model):
    """
    One trip planning request submitted by a driver.
    The planner computes stops and ELD sheets from the inputs.
    """

    class StatusChoices(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        COMPUTED  = 'computed',  'Computed'
        FAILED    = 'failed',    'Failed'

    driver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='trips',
        limit_choices_to={'is_driver': True},
    )

    # --- Inputs ---
    current_location   = models.CharField(max_length=255)
    pickup_location    = models.CharField(max_length=255)
    dropoff_location   = models.CharField(max_length=255)
    current_cycle_used = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text='Hours already used in the current 70hr/8-day cycle.',
    )

    # Start datetime — when the driver departs current_location.
    # Defaults to trip creation time; can be overridden.
    departure_time = models.DateTimeField()

    # --- Outputs (filled by planner) ---
    status        = models.CharField(max_length=10, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    error_message = models.TextField(blank=True)

    # Serialised route GeoJSON (LineString) returned by the map API —
    # stored so the frontend can render it without re-fetching.
    route_geojson = models.JSONField(null=True, blank=True)

    # Total trip distance in miles and estimated driving time in hours
    total_distance_miles = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_driving_hours  = models.DecimalField(max_digits=8,  decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Trip #{self.pk} — {self.driver.email} | {self.current_location} → {self.dropoff_location}"


class TripStop(models.Model):
    """
    One waypoint on the computed route, in sequence order.
    Covers: start, pickup, fuel stops, required rest breaks,
    10hr sleeper breaks, and the final dropoff.
    """

    class StopType(models.TextChoices):
        START         = 'start',        'Start'
        PICKUP        = 'pickup',        'Pickup'
        FUEL          = 'fuel',          'Fuel Stop'
        REST_BREAK    = 'rest_break',    '30-min Rest Break'
        SLEEPER_BREAK = 'sleeper_break', '10-hr Sleeper Break'
        DROPOFF       = 'dropoff',       'Dropoff'

    trip        = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='stops')
    sequence    = models.PositiveIntegerField()
    stop_type   = models.CharField(max_length=20, choices=StopType.choices)
    location    = models.CharField(max_length=255)
    latitude    = models.FloatField(null=True, blank=True)
    longitude   = models.FloatField(null=True, blank=True)

    # Miles from the previous stop
    miles_from_prev = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    # Cumulative miles from trip start
    cumulative_miles = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Wall-clock arrival and departure at this stop
    arrival_time   = models.DateTimeField(null=True, blank=True)
    departure_time = models.DateTimeField(null=True, blank=True)

    # Duration spent at this stop in hours (0 for pure waypoints)
    duration_hours = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['trip', 'sequence']
        unique_together = [('trip', 'sequence')]

    def __str__(self):
        return f"Trip #{self.trip_id} stop {self.sequence} ({self.get_stop_type_display()}) — {self.location}"


class TripDayLog(models.Model):
    """
    Links a Trip to the DayLog(s) generated for it.
    A trip spanning multiple days produces one DayLog per day.
    """
    trip    = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='day_logs')
    day_log = models.ForeignKey('logApi.DayLog', on_delete=models.CASCADE, related_name='trips')
    day_number = models.PositiveIntegerField(help_text='1-based day number within the trip.')

    class Meta:
        ordering = ['trip', 'day_number']
        unique_together = [('trip', 'day_log')]