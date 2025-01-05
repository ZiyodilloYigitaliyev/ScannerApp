from django.contrib import admin
from django.urls import path
from main.views import ProcessZipFileView
from question.views import GenerateRandomQuestionsView
from respons.views import login_page, register_page, dashboard, download_zip_view

urlpatterns = [
    path("api/questions", GenerateRandomQuestionsView.as_view()),
    path('admin/', admin.site.urls),
    path('upload/', ProcessZipFileView.as_view(), name='process-zip'),
    path('login/', login_page, name='login-page'),
    path('register/', register_page, name='login-page'),
    path('dashboard/', dashboard, name='dashboard'),
    path('download-zip/', download_zip_view, name='download_zip'),
]
