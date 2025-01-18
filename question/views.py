from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import QuestionList, Question, Zip
from .serializers import QuestionListSerializer, ZipSerializer
from rest_framework.permissions import AllowAny
import random
import re
from django.conf import settings
from tempfile import NamedTemporaryFile
from rest_framework.parsers import MultiPartParser, FormParser
import boto3
from bs4 import BeautifulSoup
import zipfile
import os
from django.utils.dateparse import parse_datetime

class HTMLFromZipView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def find_red_class(self, soup):
        style_tags = soup.find_all("style")
        for style_tag in style_tags:
            styles = style_tag.string
            if styles:
                matches = re.findall(r'\.(\w+)\s*{[^}]*color:\s*#ff0000\s*;?', styles, re.IGNORECASE)
                if matches:
                    return matches[0]
        return None

    def post(self, request, *args, **kwargs):
        zip_file = request.FILES.get('file')
        if not zip_file:
            return Response({"error": "ZIP fayl topilmadi"}, status=400)

        # Kategoriya va mavzu tekshiruvi
        category = request.data.get('category')
        subject = request.data.get('subject')

        if not category or not subject:
            return Response(
                {"error": "Category va Subject majburiy maydonlardir."},
                status=400
            )

        # ZIP faylni ochish
        with zipfile.ZipFile(zip_file, 'r') as z:
            html_file = None
            images = {}

            for file_name in z.namelist():
                if file_name.endswith('.html'):
                    html_file = z.read(file_name).decode('utf-8')
                elif file_name.startswith('images/'):
                    images[file_name] = z.read(file_name)

            if not html_file:
                return Response({"error": "HTML fayl ZIP ichida topilmadi"}, status=400)

        # Rasmlarni yuklash uchun S3 sozlamalari
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        image_urls = {}

        def upload_image_to_s3(image_name, image_data):
            temp_file = NamedTemporaryFile(delete=False)
            temp_file.write(image_data)
            temp_file.close()
            s3_key = f'images/{os.path.basename(image_name)}'
            s3_client.upload_file(temp_file.name, bucket_name, s3_key)
            os.unlink(temp_file.name)
            return f'https://{bucket_name}.s3.amazonaws.com/{s3_key}'

        for img_name, img_data in images.items():
            if img_name not in image_urls:
                image_urls[img_name] = upload_image_to_s3(img_name, img_data)

        # HTML faylni qayta ishlash
        soup = BeautifulSoup(html_file, 'html.parser')
        red_class = self.find_red_class(soup)
        questions = []
        current_question = None

        for p_tag in soup.find_all('p'):
            text = p_tag.get_text(strip=True)
            if not text:
                continue

            for img_tag in p_tag.find_all('img'):
                img_src = img_tag.get('src')
                if img_src in image_urls:
                    img_tag['src'] = image_urls[img_src]

            if text[0].isdigit() and '.' in text:
                if current_question:
                    questions.append(current_question)
                current_question = {
                    "text": str(p_tag),
                    "options": "",
                    "true_answer": None,
                    "category": category,
                    "subject": subject
                }
            elif text.startswith(("A)", "B)", "C)", "D)")):
                if current_question:
                    current_question["options"] += str(p_tag)

                    if red_class:
                        span_tags = p_tag.find_all("span", class_=red_class)
                        if span_tags:
                            current_question["true_answer"] = text[0]

        if current_question:
            questions.append(current_question)

        for question_data in questions:
            Zip.objects.create(
                text=question_data["text"],
                options=question_data["options"],
                true_answer=question_data["true_answer"],
                category=question_data["category"],
                subject=question_data["subject"]
            )

        return Response({"message": "Savollar ma'lumotlar bazasiga muvaffaqiyatli saqlandi."}, status=201)

class FilterQuestionsView(APIView):
    def get(self, request, *args, **kwargs):
        id_list = request.query_params.getlist('id')  # Idlarni ro'yxat ko'rinishida olish
        category = request.query_params.get('category')
        subject = request.query_params.get('subject')
        date = request.query_params.get('date')

        questions = Zip.objects.all()
        
        if category:
            questions = questions.filter(category__iexact=category)
        if subject:
            questions = questions.filter(subject__iexact=subject)
        if id_list:
            questions = questions.filter(id__in=id_list)
        if date:
            try:
                parsed_date = parse_datetime(date)
                if parsed_date:
                    questions = questions.filter(date__date=parsed_date.date())
                else:
                    return Response({"error": "Invalid date format. Use ISO 8601 format."}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ZipSerializer(questions, many=True)
        return Response({"questions": serializer.data}, status=status.HTTP_200_OK)   

class ListQuestionsView(APIView):
    def get(self, request):
        questions = Zip.objects.all()
        serializer = ZipSerializer(questions, many=True)
        grouped_questions = {}
        for question in serializer.data:
            category = question['category']
            if category not in grouped_questions:
                grouped_questions[category] = []
            grouped_questions[category].append(question)
        return Response({"data": grouped_questions})


class DeleteAllQuestionsView(APIView):
    def delete(self, request):
        Zip.objects.all().delete()
        return Response({"message": "All questions have been deleted successfully."}, status=status.HTTP_200_OK)



class GenerateRandomQuestionsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        try:    
            question_lists = QuestionList.objects.prefetch_related('questions').all()
            serializer = QuestionListSerializer(question_lists, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


    
    def get_next_list_id(self):
        last_id_obj, created = QuestionList.objects.get_or_create(id=1)
        next_id = last_id_obj.last_id + 1
        last_id_obj.last_id = next_id
        last_id_obj.save()
        return next_id
       

    def post(self, request):
        try:
            if isinstance(request.data, list):
                request_data = request.data[0]
            else:
                request_data = request.data
            questions_num = request_data.get('num', {})
            questions_data = request_data.get('data', {})
            additional_value = questions_num.get('additional_value')
            questions_class = questions_num.get('class')

            majburiy_fan_1 = questions_data.get('Majburiy_Fan_1', [])
            majburiy_fan_2 = questions_data.get('Majburiy_Fan_2', [])
            majburiy_fan_3 = questions_data.get('Majburiy_Fan_3', [])
            fan_1 = questions_data.get('Fan_1', [])
            fan_2 = questions_data.get('Fan_2', [])

            final_lists = []
            for _ in range(additional_value):
                new_list = {
                    "Majburiy_Fan_1": self.clean_questions(self.get_random_items(majburiy_fan_1, 10)),
                    "Majburiy_Fan_2": self.clean_questions(self.get_random_items(majburiy_fan_2, 10)),
                    "Majburiy_Fan_3": self.clean_questions(self.get_random_items(majburiy_fan_3, 10)),
                    "Fan_1": self.clean_questions(self.get_random_items(fan_1, 30)),
                    "Fan_2": self.clean_questions(self.get_random_items(fan_2, 30)),
                }

                list_id = self.get_next_list_id()
                final_questions = {category: [] for category in new_list.keys()}
                global_order_counter = 1

                for category, questions in new_list.items():
                    for question in questions:
                        final_questions[category].append({
                            "category": category,
                            "subject": question.get("subject", ""),
                            "text": question["text"],
                            "options": question.get("options", ""),
                            "true_answer": question.get("true_answer", ""),
                            "image": question.get("image", None),
                            "order": global_order_counter,
                        })
                        global_order_counter += 1

                final_lists.append({
                    "list_id": list_id,
                    "questions": final_questions
                })

                try:
                    question_list = QuestionList.objects.create(list_id=list_id, questions_class=questions_class)
                    for category, questions in final_questions.items():
                        for question in questions:
                            Question.objects.create(
                                list=question_list,
                                category=category,
                                subject=question.get('subject', ""),
                                text=question.get('text', ""),
                                options=question.get('options', ""),
                                image=question.get('image', None),
                                question_id=question.get('order'),
                                true_answer=question.get('true_answer', ""),
                            )
                except Exception as e:
                    print(f"Error during database save: {e}")
                    return Response({"error": "Database save error"}, status=status.HTTP_400_BAD_REQUEST)

            return Response(final_lists, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def get_random_items(source_list, count):
        if not source_list:
            return []
        count = min(count, len(source_list))
        return random.sample(source_list, count)

    @staticmethod
    def clean_questions(questions):
        for question in questions:
            question['text'] = re.sub(r'^\d+\.\s*', '', question['text'])
        return questions
