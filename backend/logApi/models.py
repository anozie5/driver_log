from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q, F
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()


VALID_MINUTES = {0, 15, 30, 45}


class DayLog(models.Model):
    """
    One log per driver per calendar day.
    Mirrors the paper Drivers Daily Log form.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='day_logs',
        limit_choices_to={'is_driver': True},
    )
    day = models.DateField()

    # Header fields (top of the paper form)
    from_location = models.TextField()
    to_location = models.TextField()
    vehicle_number = models.CharField(max_length=50, blank=True)
    carrier_name = models.CharField(max_length=255, blank=True)
    main_office_address = models.TextField(blank=True)
    home_terminal_address = models.TextField(blank=True)

    # Totals row (computed from ActLogs but stored for quick reads)
    total_miles_driven = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_mileage = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_hours_driving = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    total_hours_on_duty = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    total_hours_off_duty = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    total_hours_sleeping = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    remarks = models.TextField(blank=True)
    shipping_documents = models.TextField(blank=True)
    dvl_or_manifest_no = models.CharField(max_length=100, blank=True)
    shipper_commodity = models.CharField(max_length=255, blank=True)

    # Co-driver workflow fields
    co_driver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='co_driven_logs',
        blank=True,
        null=True,
        limit_choices_to={'is_driver': True},
    )
    co_driver_miles_driven = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # The co-driver fills their own DayLog and marks it as a co-driver entry
    # pointing to the main driver's log. The main driver then approves.
    is_co_driver_entry = models.BooleanField(default=False)
    linked_primary_log = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='co_driver_submissions',
        blank=True,
        null=True,
        help_text="Set by a co-driver to link their log to the main driver's log.",
    )
    co_driver_approved = models.BooleanField(
        null=True,
        blank=True,
        help_text="Null = pending, True = approved, False = rejected.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # One log per driver per day (not globally unique by day)
        unique_together = [('user', 'day')]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['user', 'day']),
            models.Index(fields=['day']),
        ]
        ordering = ['day']

    def __str__(self):
        return f"{self.user.email} — {self.day}"


class ActLog(models.Model):
    """
    A single activity segment within a DayLog.
    Maps to one coloured band on the 24-hour grid of the paper form.
    Times must be on 15-minute boundaries and start < end.
    """

    class ActivityType(models.TextChoices):
        OFF_DUTY = 'OF', 'Off Duty'
        SLEEPER_BERTH = 'SB', 'Sleeper Berth'
        DRIVING = 'D', 'Driving'
        ON_DUTY = 'ON', 'On Duty (Not Driving)'

    day_log = models.ForeignKey(
        DayLog,
        on_delete=models.CASCADE,
        related_name='act_logs',
    )
    activity = models.CharField(
        max_length=2,
        choices=ActivityType.choices,
        verbose_name='Activity',
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['day_log']),
            models.Index(fields=['day_log', 'start_time']),
        ]
        ordering = ['day_log', 'start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['day_log', 'start_time', 'end_time'],
                name='unique_actlog_per_range'
            ),
            models.CheckConstraint(
                condition=Q(start_time__lt=F('end_time')),
                name='actlog_start_before_end',
            ),
        ]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_quarter_hour(self, dt, field_name):
        if dt.minute not in VALID_MINUTES or dt.second != 0 or dt.microsecond != 0:
            raise ValidationError({
                field_name: (
                    f"Time must be on a 15-minute boundary (:00, :15, :30, :45). "
                    f"Got {dt.strftime('%H:%M:%S')}."
                )
            })

    def clean(self):
        if self.start_time and self.end_time:
            self._validate_quarter_hour(self.start_time, 'start_time')
            self._validate_quarter_hour(self.end_time, 'end_time')

            if self.start_time >= self.end_time:
                raise ValidationError({'end_time': 'End time must be strictly after start time.'})

            # Prevent overlapping segments for the same DayLog
            qs = ActLog.objects.filter(
                day_log=self.day_log,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    'This time range overlaps with an existing activity on the same log.'
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.day_log.user.email} | {self.get_activity_display()} | "
            f"{self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')}"
        )