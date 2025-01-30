from django.urls import path
from .views import generate_question_pdf

urlpatterns = [
    path('generate-pdf/', generate_question_pdf, name='generate_question_pdf'),
]