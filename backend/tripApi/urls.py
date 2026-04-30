from django.urls import path
from tripApi.views import *

urlpatterns = [
    # List all trips / create a new trip
    path('trips/', TripListView.as_view(), name='trip-list'),

    # Retrieve or delete a specific trip
    path('trips/<int:pk>/', TripDetailView.as_view(), name='trip-detail'),

    # Re-run the planner for an existing trip (POST to sub-action)
    path('trips/<int:pk>/replan/', TripDetailView.as_view(), name='trip-replan'),
]