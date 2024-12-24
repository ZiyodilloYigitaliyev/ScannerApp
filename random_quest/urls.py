from django.urls import path
from .views import RandomizedQuestionsView

urlpatterns = [
    path("random-questions/", RandomizedQuestionsView.as_view(), name="randomized-questions"),
]
