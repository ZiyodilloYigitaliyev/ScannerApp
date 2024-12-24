from django.contrib import admin
from django.urls import path, include
from main.views import ProcessZipFileView


urlpatterns = [
    path("", include("random_quest.urls")),
    path('admin/', admin.site.urls),
    path('upload/', ProcessZipFileView.as_view(), name='process-zip'),
]
