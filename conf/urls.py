"""
URL configuration for conf project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from main.views import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/upload/', UploadZipView.as_view(), name='upload_zip'),
    path('api/upload-docx/', UploadDocxView.as_view(), name='upload_docx'),
]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# Static va media fayllarni S3'dan olish
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)