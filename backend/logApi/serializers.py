from rest_framework import serializers

from logApi.models import DayLog, ActLog
from logApi.exceptions import InvalidTimeRangeError, TimeRangeOverlapError
from logApi.utils import validate_15_minute_interval, create_act_log, update_act_log
from authApi.models import User


# ---------------------------------------------------------------------------
# ActLog
# ---------------------------------------------------------------------------

class ActLogSerializer(serializers.ModelSerializer):
    """Serializes a single activity segment."""

    activity_display = serializers.CharField(source='get_activity_display', read_only=True)
    duration_hours = serializers.SerializerMethodField()

    class Meta:
        model = ActLog
        fields = [
            'id',
            'day_log',
            'activity',
            'activity_display',
            'start_time',
            'end_time',
            'duration_hours',
            'location',
            'remarks',
        ]
        read_only_fields = ['id', 'activity_display', 'duration_hours']

    def get_duration_hours(self, obj):
        delta = obj.end_time - obj.start_time
        return round(delta.total_seconds() / 3600, 2)

    # -- field-level validation --

    def validate_start_time(self, value):
        validate_15_minute_interval(value)
        return value

    def validate_end_time(self, value):
        validate_15_minute_interval(value)
        return value

    def validate(self, data):
        start = data.get('start_time', getattr(self.instance, 'start_time', None))
        end = data.get('end_time', getattr(self.instance, 'end_time', None))
        if start and end and start >= end:
            raise InvalidTimeRangeError('Start time must be strictly before end time.')
        return data

    def create(self, validated_data):
        return create_act_log(
            day_log=validated_data['day_log'],
            activity=validated_data['activity'],
            start_time=validated_data['start_time'],
            end_time=validated_data['end_time'],
            location=validated_data.get('location', ''),
            remarks=validated_data.get('remarks', ''),
        )

    def update(self, instance, validated_data):
        return update_act_log(
            act=instance,
            activity=validated_data.get('activity'),
            start_time=validated_data.get('start_time'),
            end_time=validated_data.get('end_time'),
            location=validated_data.get('location'),
            remarks=validated_data.get('remarks'),
        )


# ---------------------------------------------------------------------------
# DayLog — lightweight list view
# ---------------------------------------------------------------------------

class DayLogListSerializer(serializers.ModelSerializer):
    """
    Compact representation used when listing many logs (e.g. weekly/monthly views).
    Does NOT embed act_logs to keep the payload small.
    """

    driver_email = serializers.EmailField(source='user.email', read_only=True)
    driver_name = serializers.SerializerMethodField()
    co_driver_email = serializers.EmailField(source='co_driver.email', read_only=True, default=None)
    co_driver_name = serializers.SerializerMethodField()
    co_driver_approval_status = serializers.SerializerMethodField()

    class Meta:
        model = DayLog
        fields = [
            'id',
            'day',
            'driver_email',
            'driver_name',
            'co_driver_email',
            'co_driver_name',
            'co_driver_approval_status',
            'from_location',
            'to_location',
            'vehicle_number',
            'total_miles_driven',
            'total_hours_driving',
            'total_hours_on_duty',
            'total_hours_off_duty',
            'total_hours_sleeping',
            'is_co_driver_entry',
            'co_driver_approved',
        ]
        read_only_fields = fields

    def get_driver_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email

    def get_co_driver_name(self, obj):
        if obj.co_driver:
            return f"{obj.co_driver.first_name} {obj.co_driver.last_name}".strip() or obj.co_driver.email
        return None

    def get_co_driver_approval_status(self, obj):
        if obj.co_driver_approved is None and obj.is_co_driver_entry:
            return 'pending'
        if obj.co_driver_approved is True:
            return 'approved'
        if obj.co_driver_approved is False:
            return 'rejected'
        return None


# ---------------------------------------------------------------------------
# DayLog — full detail view
# ---------------------------------------------------------------------------

class DayLogDetailSerializer(serializers.ModelSerializer):
    """
    Full log with embedded act_logs.
    Used for GET /logs/<id>/ and POST/PATCH.
    """

    act_logs = ActLogSerializer(many=True, read_only=True)
    driver_email = serializers.EmailField(source='user.email', read_only=True)
    driver_name = serializers.SerializerMethodField()
    co_driver_email = serializers.EmailField(source='co_driver.email', read_only=True, default=None)
    co_driver_approval_status = serializers.SerializerMethodField()

    # Write-only: accept co_driver by PK
    co_driver_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_driver=True),
        source='co_driver',
        write_only=True,
        required=False,
        allow_null=True,
    )
    linked_primary_log_id = serializers.PrimaryKeyRelatedField(
        queryset=DayLog.objects.all(),
        source='linked_primary_log',
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = DayLog
        fields = [
            'id',
            'day',
            'driver_email',
            'driver_name',
            # header
            'from_location',
            'to_location',
            'vehicle_number',
            'carrier_name',
            'main_office_address',
            'home_terminal_address',
            # totals
            'total_miles_driven',
            'total_mileage',
            'co_driver_miles_driven',
            'total_hours_driving',
            'total_hours_on_duty',
            'total_hours_off_duty',
            'total_hours_sleeping',
            # remarks / docs
            'remarks',
            'shipping_documents',
            'dvl_or_manifest_no',
            'shipper_commodity',
            # co-driver
            'co_driver_email',
            'co_driver_id',
            'co_driver_approval_status',
            'is_co_driver_entry',
            'co_driver_approved',
            'linked_primary_log_id',
            # activity grid
            'act_logs',
            # timestamps
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'driver_email', 'driver_name', 'co_driver_email',
            'co_driver_approval_status', 'act_logs', 'created_at', 'updated_at',
        ]

    def get_driver_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email

    def get_co_driver_approval_status(self, obj):
        if obj.co_driver_approved is None and obj.is_co_driver_entry:
            return 'pending'
        if obj.co_driver_approved is True:
            return 'approved'
        if obj.co_driver_approved is False:
            return 'rejected'
        return None

    def validate(self, data):
        # A co-driver entry must point to a primary log for the same day
        linked = data.get('linked_primary_log', self.instance and self.instance.linked_primary_log)
        is_co = data.get('is_co_driver_entry', self.instance and self.instance.is_co_driver_entry)
        day = data.get('day', self.instance and self.instance.day)

        if is_co and linked and day and linked.day != day:
            raise serializers.ValidationError(
                'linked_primary_log must be a log for the same day as this log.'
            )
        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Prevent a driver from changing another user's log user field
        validated_data.pop('user', None)
        return super().update(instance, validated_data)


# ---------------------------------------------------------------------------
# Co-driver approval (PATCH payload)
# ---------------------------------------------------------------------------

class CoDriverApprovalSerializer(serializers.Serializer):
    """
    Used by the main driver to approve or reject a co-driver submission.
    PATCH /logs/<primary_log_id>/co-driver-approval/
    Body: { "co_driver_log_id": <int>, "approve": true|false }
    """
    co_driver_log_id = serializers.IntegerField()
    approve = serializers.BooleanField()