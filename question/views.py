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
from datetime import *


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
            list_id = request.query_params.get('list_id', None)
            questions_class = request.query_params.get('questions_class', None)
            limit = request.query_params.get('limit', None)
            date = request.query_params.get('date', None)
            questions_filter = request.query_params.get('questions_filter', None)  # Yangi filter qo'shildi

            # Barcha question_lists ma'lumotlarini olish
            question_lists = QuestionList.objects.prefetch_related('questions').all()

            # list_id bo'yicha filter
            if list_id:
                question_lists = question_lists.filter(list_id=list_id)
            
            # questions_class bo'yicha filter
            if questions_class:
                question_lists = question_lists.filter(questions_class=questions_class)
            
            # date bo'yicha filter
            if date:
                try:
                    # ISO 8601 formatdagi datetime qiymatini parse qilish
                    date_time = datetime.fromisoformat(date.replace("Z", "+00:00"))
                    question_lists = question_lists.filter(created_at=date_time)
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use ISO 8601 format: YYYY-MM-DDTHH:MM:SS.ssssssZ."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Ma'lumotlarni tayyorlash
            response_data = []
            for question_list in question_lists:
                list_data = {
                    "list_id": question_list.list_id,
                    "questions_class": question_list.questions_class,
                    "created_at": question_list.created_at,
                }

                # questions_filter ga ko'ra "questions" ni qo'shish
                if not questions_filter or questions_filter.lower() != "false":
                    list_data["questions"] = []
                    questions = question_list.questions.all()

                    # Limitni qo'llash
                    if limit:
                        try:
                            limit = int(limit)
                            questions = questions[:limit]
                        except ValueError:
                            return Response({"error": "Invalid limit value. It should be an integer."}, status=status.HTTP_400_BAD_REQUEST)

                    for idx, question in enumerate (questions, start=1):
                        list_data["questions"].append({
                            "id": question.id,
                            "category": question.category,
                            "subject": question.subject,
                            "text": question.text,
                            "options": question.options,
                            "true_answer": question.true_answer,
                            "list": question_list.id,
                            "order": idx,
                        })

                response_data.append(list_data)

            # Faqat oxirgi ro'yxatni qaytarish
            return Response(response_data[-1] if response_data else {}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        try:
            request_data = request.data

            final_lists = []
            for item in request_data:
                questions_num = item.get("num", {})
                questions_data = item.get("data", {})
                additional_value = questions_num.get("additional_value", 0)
                questions_class = questions_num.get("class", None)

                # Har bir ro'yxat uchun ishlov berish
                for _ in range(additional_value):
                    list_id = self.get_next_list_id()

                    # Har bir kategoriya bo'yicha savollarni qayta ishlash
                    final_questions = {key: [] for key in questions_data.keys()}
                    global_order_counter = 1

                    for category, questions in questions_data.items():
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

                    # Natijalarni saqlash
                    final_lists.append({
                        "list_id": list_id,
                        "questions_class": questions_class,
                        "questions": final_questions,
                        "order": global_order_counter,
                    })

                    # Ma'lumotlar bazasiga saqlash
                    try:
                        question_list = QuestionList.objects.create(list_id=list_id, questions_class=questions_class)
                        for category, questions in final_questions.items():
                            for question in questions:
                                Question.objects.create(
                                    list=question_list,
                                    category=category,
                                    subject=question.get("subject", ""),
                                    text=question.get("text", ""),
                                    options=question.get("options", ""),
                                    true_answer=question.get("true_answer", ""),
                                    global_order_counter=global_order_counter,
                                )
                    except Exception as e:
                        print(f"Error during database save: {e}")
                        return Response({"error": "Database save error"}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"success": "Malumotlar Muvofaqiyatli Saqlandi"}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


    def get_next_list_id(self):
        last_list = QuestionList.objects.last()
        next_id = last_list.list_id + 1 if last_list else 100001
        QuestionList.objects.create(list_id=next_id)
        return next_id


    @staticmethod
    def get_random_items(source_list, count):
        if not source_list:
            return []
        count = min(count, len(source_list))
        return random.sample(source_list, count)

    # @staticmethod
    # def clean_questions(questions):
    #     for question in questions:
    #         question['text'] = re.sub(r'^\d+\.\s*', '', question['text'])
    #     return questions
