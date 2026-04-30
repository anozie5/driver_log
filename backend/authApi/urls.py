from django.urls import path
from authApi.views import (
    SignUpView,
    LogInView,
    UserProfileView,
    PasswordResetView,
    EmailChangeView
)

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('login/', LogInView.as_view(), name='login'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('password-reset/', PasswordResetView.as_view(), name='password'),
    path('change-email/', EmailChangeView.as_view(), name='email'),
]