from django.contrib import admin
from django.urls import path, include
from main.views import ProcessZipFileView
from question.views import GenerateRandomQuestionsView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    
    path("savol/", include("question.urls")),
    path("api/questions", GenerateRandomQuestionsView.as_view()),
    path('admin/', admin.site.urls),
    path('upload/', ProcessZipFileView.as_view(), name='process-zip'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
