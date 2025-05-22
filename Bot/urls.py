from django.urls import path
from .views import *
from . import views
urlpatterns = [
    path('check-user/', CheckUserAPIView.as_view(), name='check-user'),
    path('register-user/', RegisterUserAPIView.as_view(), name='register-user'),
    path('all-dates/', BotAllDatesAPIView.as_view(), name='get-all-dates'),
    path("channel-stats/", ChannelStatsView.as_view(), name="channel-stats"),
    path('users/id/', views.get_all_user_ids, name='get_all_user_ids'),
]
