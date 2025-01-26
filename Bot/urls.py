from django.urls import path
from .views import CheckUserAPIView, RegisterUserAPIView

urlpatterns = [
    path('check-user/', CheckUserAPIView.as_view(), name='check-user'),
    path('register-user/', RegisterUserAPIView.as_view(), name='register-user'),
]
