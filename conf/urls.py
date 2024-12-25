from django.contrib import admin
from django.urls import path
from main.views import ProcessZipFileView
from question.views import RandomizedQuestionsView


urlpatterns = [
    path("api/questions", RandomizedQuestionsView.as_view()),
    path('admin/', admin.site.urls),
    path('upload/', ProcessZipFileView.as_view(), name='process-zip'),
]
