from django.http import HttpResponse
from django.shortcuts import render
from .utils import get_questions_from_api, generate_html_from_questions, generate_pdf

# API URL
API_URL = "https://scan-app-9206bf041b06.herokuapp.com/api/questions?question_filter=true"

def generate_question_pdf(request):
    questions_data = get_questions_from_api(API_URL)
    if not questions_data:
        return HttpResponse("Savollarni olishda xatolik yuz berdi.", status=500)
    
    html_content = generate_html_from_questions(questions_data)
    response = generate_pdf(html_content)
    return response