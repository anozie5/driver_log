from rest_framework import serializers
from django.utils import timezone

from tripApi.models import Trip, TripStop, TripDayLog
from logApi.serializers import DayLogDetailSerializer


class TripStopSerializer(serializers.ModelSerializer):
    stop_type_display = serializers.CharField(source='get_stop_type_display', read_only=True)

    class Meta:
        model = TripStop
        fields = [
            'id', 'sequence', 'stop_type', 'stop_type_display',
            'location', 'latitude', 'longitude',
            'miles_from_prev', 'cumulative_miles',
            'arrival_time', 'departure_time', 'duration_hours',
            'notes',
        ]


class TripDayLogSerializer(serializers.ModelSerializer):
    day_log = DayLogDetailSerializer(read_only=True)

    class Meta:
        model = TripDayLog
        fields = ['day_number', 'day_log']


class TripCreateSerializer(serializers.ModelSerializer):
    """Used for POST /trips/ — accepts the four driver inputs."""

    class Meta:
        model = Trip
        fields = [
            'current_location',
            'pickup_location',
            'dropoff_location',
            'current_cycle_used',
            'departure_time',
        ]

    def validate_current_cycle_used(self, value):
        if value < 0 or value > 70:
            raise serializers.ValidationError('Cycle hours must be between 0 and 70.')
        return value

    def validate_departure_time(self, value):
        now = timezone.now()
        if value < now.replace(hour=0, minute=0, second=0, microsecond=0):
            raise serializers.ValidationError('Departure time cannot be in the past.')
        return value

    def create(self, validated_data):
        validated_data['driver'] = self.context['request'].user
        return super().create(validated_data)


class TripDetailSerializer(serializers.ModelSerializer):
    """Full trip output: stops, route GeoJSON, ELD day logs."""
    stops    = TripStopSerializer(many=True, read_only=True)
    day_logs = TripDayLogSerializer(many=True, read_only=True)
    driver_email = serializers.EmailField(source='driver.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Trip
        fields = [
            'id',
            'driver_email',
            'current_location',
            'pickup_location',
            'dropoff_location',
            'current_cycle_used',
            'departure_time',
            'status',
            'status_display',
            'error_message',
            'route_geojson',
            'total_distance_miles',
            'total_driving_hours',
            'stops',
            'day_logs',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class TripListSerializer(serializers.ModelSerializer):
    """Compact view for list endpoints."""
    driver_email = serializers.EmailField(source='driver.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Trip
        fields = [
            'id', 'driver_email',
            'current_location', 'pickup_location', 'dropoff_location',
            'departure_time', 'status', 'status_display',
            'total_distance_miles', 'total_driving_hours',
            'created_at',
        ]