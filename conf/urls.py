from django.contrib import admin
from django.urls import path, include
from question.views import GenerateRandomQuestionsView
from main.views import ProcessImageView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("savol/", include("question.urls")),
    path("upload/", ProcessImageView.as_view()),
    path("api/questions", GenerateRandomQuestionsView.as_view()),
    path('admin/', admin.site.urls),
    path('bot/', include('Bot.urls')),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
