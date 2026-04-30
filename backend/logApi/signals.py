from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from logApi.models import ActLog
from logApi.utils import recompute_day_log_totals


@receiver(post_save, sender=ActLog)
def actlog_saved(sender, instance, **kwargs):
    recompute_day_log_totals(instance.day_log)


@receiver(post_delete, sender=ActLog)
def actlog_deleted(sender, instance, **kwargs):
    recompute_day_log_totals(instance.day_log)