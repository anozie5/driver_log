from django.urls import path
from logApi.views import *

urlpatterns = [

    # ------------------------------------------------------------------
    # DayLog — list / create
    # ------------------------------------------------------------------
    path('logs/', DayLogListView.as_view(), name='daylog-list'),

    # ------------------------------------------------------------------
    # DayLog — detail (get / patch / delete)
    # ------------------------------------------------------------------
    path('logs/<int:pk>/', DayLogDetailView.as_view(), name='daylog-detail'),

    # ------------------------------------------------------------------
    # Co-driver workflow
    # ------------------------------------------------------------------

    # Co-driver submits their log for approval
    path('logs/<int:pk>/submit-co-driver/', CoDriverSubmitView.as_view(), name='codriver-submit'),

    # Main driver approves or rejects a co-driver submission
    path('logs/<int:pk>/approve-co-driver/', CoDriverApprovalView.as_view(), name='codriver-approve'),

    # Main driver sees all pending co-driver submissions for their logs
    path('logs/pending-co-drivers/', PendingCoDriverView.as_view(), name='codriver-pending'),

    # ------------------------------------------------------------------
    # ActLog — nested under a DayLog
    # ------------------------------------------------------------------
    path('logs/<int:day_log_id>/acts/', ActLogListView.as_view(), name='actlog-list'),
    path('acts/<int:pk>/', ActLogDetailView.as_view(), name='actlog-detail'),

    # ------------------------------------------------------------------
    # Manager — driver overviews
    # ------------------------------------------------------------------
    path('managers/drivers/', DriverOverviewView.as_view(), name='manager-drivers'),
    path('managers/drivers/<int:driver_id>/logs/', DriverOverviewView.as_view(), name='manager-driver-logs'),
]