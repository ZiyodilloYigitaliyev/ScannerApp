from django.urls import path
from .views import *

urlpatterns = [
    path('check-user/', CheckUserAPIView.as_view(), name='check-user'),
    path('register-user/', RegisterUserAPIView.as_view(), name='register-user'),
    path('all-dates/', BotAllDatesAPIView.as_views(), name='get-all-dates'),
    path("channel-stats/", ChannelStatsView.as_view(), name="channel-stats"),
]
