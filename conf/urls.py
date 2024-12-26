from django.contrib import admin
from django.urls import path
from main.views import ProcessZipFileView
from question.views import GenerateRandomQuestionsView


urlpatterns = [
    path("api/questions", GenerateRandomQuestionsView.as_view()),
    path('admin/', admin.site.urls),
    path('upload/', ProcessZipFileView.as_view(), name='process-zip'),
]
