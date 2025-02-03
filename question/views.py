import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import QuestionList, Question, Zip
from .serializers import ZipSerializer
from rest_framework.permissions import AllowAny
import random
from django.db import transaction
from bs4 import BeautifulSoup
import zipfile
from datetime import *
from rest_framework.response import Response
import logging
from django.conf import settings
import re
import boto3
from django.utils.timezone import make_aware
import uuid
from concurrent.futures import ThreadPoolExecutor
from tempfile import NamedTemporaryFile
import os
logger = logging.getLogger(__name__)

class HTMLFromZipView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        questions = Zip.objects.values("text", "options", "true_answer", "category", "subject")
        bucket_url = f'https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/'

        result = []
        for question in questions:
            soup = BeautifulSoup(question["text"], 'html.parser')
            for img_tag in soup.find_all('img'):
                img_src = img_tag.get('src')
                if img_src and img_src.startswith('images/'):
                    img_tag['src'] = f'{bucket_url}{img_src}'
            question["text"] = str(soup)
            result.append(question)

        return Response(result, status=200)

    def post(self, request, *args, **kwargs):
        zip_file = request.FILES.get('file')
        if not zip_file:
            return Response({"error": "ZIP fayl topilmadi"}, status=400)

        category, subject = request.data.get('category'), request.data.get('subject')
        if not category or not subject:
            return Response({"error": "Category va Subject majburiy maydonlardir."}, status=400)

        with zipfile.ZipFile(zip_file, 'r') as z:
            html_file, images = None, {}
            for file_name in z.namelist():
                if file_name.endswith('.html'):
                    html_file = z.read(file_name).decode('utf-8')
                elif file_name.startswith('images/'):
                    images[file_name] = z.read(file_name)

        if not html_file:
            return Response({"error": "HTML fayl ZIP ichida topilmadi"}, status=400)

        self.process_html_task(html_file, images, category, subject)
        return Response({"message": "Savollarni Yuklash Jarayoni Tugatildi"}, status=201)

    def process_html_task(self, html_file, images, category, subject):
        soup = BeautifulSoup(html_file, 'lxml')
        image_urls = self.upload_images_concurrently(images)

        for img_tag in soup.find_all('img'):
            img_src = img_tag.get('src')
            if img_src in image_urls:
                img_tag['src'] = image_urls[img_src]
            else:
                img_tag.decompose()

        key_answers = []
        for p_tag in soup.find_all('p'):
            text = p_tag.get_text(strip=True)
            if "KEY" in text.upper():
                key_answers = [match[1] for match in sorted(re.findall(r'(\d+)-([A-D])', text), key=lambda x: int(x[0]))]
                break

        questions, current_question = [], None
        question_counter = 0

        for tag in soup.find_all(['p', 'div']):
            text = tag.get_text(strip=True)
            if not text:
                continue

            if re.match(r'^\d+\.', text):
                if current_question:
                    questions.append(current_question)
                question_counter += 1
                current_question = {
                        "text": str(tag),
                        "options": "",
                        "true_answer": None,
                        "category": category,
                        "subject": subject
                    }
            elif re.match(r'^[A-D]\)', text) and current_question:
                current_question["options"] += str(tag)

        if current_question:
            questions.append(current_question)

        for i, question in enumerate(questions):
            if i < len(key_answers):
                question["true_answer"] = key_answers[i]

        Zip.objects.bulk_create([Zip(**q) for q in questions])

        return f"{len(questions)} ta savol muvaffaqiyatli qayta ishlangan!"

    def upload_images_concurrently(self, images):
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self.upload_image_to_s3, img_name, img_data): img_name for img_name, img_data in images.items()}
            return {img_name: future.result() for future, img_name in futures.items()}

    def upload_image_to_s3(self, image_name, image_data):
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        file_name, file_extension = os.path.splitext(image_name)
        unique_name = f"images/{uuid.uuid4().hex}{file_extension}"

        with NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(image_data)
            temp_file.close()
            s3_client.upload_file(temp_file.name, bucket_name, unique_name, ExtraArgs={"ACL": "public-read"})
            os.unlink(temp_file.name)

        return f'https://{bucket_name}.s3.amazonaws.com/{unique_name}'





class ListQuestionsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        questions = Zip.objects.all()
        serializer = ZipSerializer(questions, many=True)
        grouped_questions = {}
        for question in serializer.data:
            category = question["category"]
            if category not in grouped_questions:
                grouped_questions[category] = []
            grouped_questions[category].append(question)
        return Response({"data": grouped_questions})


class DeleteAllQuestionsView(APIView):
    permission_classes = [AllowAny]
    
    def delete(self, request):
        Zip.objects.all().delete()
        return Response(
            {"message": "All questions have been deleted successfully."},
            status=status.HTTP_200_OK,
        )



class GenerateRandomQuestionsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        try:
            list_id = request.query_params.get('list_id', None)
            question_class = request.query_params.get('question_class', None)
            date = request.query_params.get('date', None)
            category = request.query_params.get('category', None)
            question_filter = request.query_params.get('question_filter', '').lower() == 'true'
            questions_only = request.query_params.get('questions_only', '').lower() == 'true'

            question_lists = QuestionList.objects.prefetch_related('questions').all()

            if list_id:
                question_lists = question_lists.filter(list_id=list_id)
            if question_class:
                question_lists = question_lists.filter(question_class=question_class)
            if date:
                try:
                    filter_date = datetime.strptime(date, "%Y-%m-%d").date()
                    question_lists = question_lists.filter(created_at__date=filter_date)
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use YYYY-MM-DD."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            response_data = []
            for question_list in question_lists:
                category_order = [
                    "Majburiy_Fan_1",
                    "Majburiy_Fan_2",
                    "Majburiy_Fan_3",
                    "Fan_1",
                    "Fan_2"
                ]
                all_questions = question_list.questions.all()
                if category:
                    all_questions = all_questions.filter(category=category)
                grouped_questions = {}
                for q in all_questions:
                    grouped_questions.setdefault(q.category, []).append(q)
                ordered_questions = []
                for cat in category_order:
                    if cat in grouped_questions:
                        random.shuffle(grouped_questions[cat])
                        ordered_questions.extend(grouped_questions[cat])
                final_questions = [
                    {
                        "id": q.id,
                        "category": q.category,
                        "text": q.text,
                        "options": q.options,
                        "subject": q.subject,
                        "true_answer": q.true_answer,
                        "list": q.list_id,
                        "order": idx + 1
                    }
                    for idx, q in enumerate(ordered_questions)
                ]
                list_data = {
                    "list_id": question_list.list_id,
                    "question_class": question_list.question_class,
                    "created_at": question_list.created_at,
                    "questions": final_questions,
                    "categories": list(grouped_questions.keys())
                }
                if questions_only:
                    del list_data["questions"]
                response_data.append(list_data)

            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    def post(self, request):
        try:
            # Agar yuborilgan ma'lumot ro'yxat shaklida bo'lsa, birinchi elementni olamiz
            if isinstance(request.data, list):
                request_data = request.data[0]
            else:
                request_data = request.data

            questions_num = request_data.get("num", {})

            if "list_id" in questions_num and questions_num["list_id"] is not None:
                updated_list_id = questions_num["list_id"] + 1
            else:
                updated_list_id = 100000

            # Qayta takrorlanmasligini tekshirish: agar hozirgi updated_list_id bazada mavjud bo'lsa, oshirib boramiz.
            while QuestionList.objects.filter(list_id=updated_list_id).exists():
                updated_list_id += 1

            questions_data = request_data.get("data", {})
            additional_value = questions_num.get("additional_value", 0)
            question_class = questions_num.get("class", "")

            category_structure = {
                "Majburiy_Fan_1": questions_data.get("Majburiy_Fan_1", []),
                "Majburiy_Fan_2": questions_data.get("Majburiy_Fan_2", []),
                "Majburiy_Fan_3": questions_data.get("Majburiy_Fan_3", []),
                "Fan_1": questions_data.get("Fan_1", []),
                "Fan_2": questions_data.get("Fan_2", []),
            }

            final_lists = []

            # Har bir yangi list uchun: (agar additional_value bir nechta bo'lsa, har biri uchun alohida list yaratiladi)
            for _ in range(additional_value):
                # Shu yerda updated_list_id ga nisbatan yagona list_id olinadi
                while QuestionList.objects.filter(list_id=updated_list_id).exists():
                    updated_list_id += 1
                list_id = updated_list_id

                final_questions = []
                for category in category_structure.keys():
                    questions = category_structure[category]
                    if not questions:
                        continue
                    random_questions = self.get_random_items(questions, 10 if "Majburiy" in category else 30)
                    for idx, q in enumerate(random_questions):
                        final_questions.append({
                            "category": category,
                            "subject": q.get("subject", ""),
                            "text": q.get("text", ""),
                            "options": q.get("options", ""),
                            "true_answer": q.get("true_answer", ""),
                            "order": idx + 1,
                        })
                final_lists.append({
                    "list_id": list_id,
                    "questions": final_questions,
                    "question_class": question_class,
                })

                try:
                    with transaction.atomic():
                        question_list = QuestionList.objects.create(
                            list_id=list_id, question_class=question_class
                        )
                        for question in final_questions:
                            Question.objects.create(
                                list=question_list,
                                category=question.get("category", ""),
                                subject=question.get("subject", ""),
                                text=question.get("text", ""),
                                options=question.get("options", ""),
                                true_answer=question.get("true_answer", ""),
                                order=question.get("order"),
                            )
                except Exception as e:
                    print("Database save error:", e)
                    return Response(
                        {"error": f"Database save error: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Keyingi list uchun updated_list_id ni 1 ga oshiramiz
                updated_list_id += 1

            return Response(
                {"success": "Questions saved successfully", "data": final_lists},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def delete(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                QuestionList.objects.all().delete()
            return Response(
                {"success": "All data from ModelName has been deleted successfully."},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": f"An error occurred during deletion: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    
    @staticmethod
    def get_random_items(source_list, count):
        if not source_list:
            return []
        count = min(count, len(source_list))
        return random.sample(source_list, count)
    
    


