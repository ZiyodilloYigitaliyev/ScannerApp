from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import QuestionList, Question, Zip
from .serializers import ZipSerializer
from rest_framework.permissions import AllowAny
import random
from django.db import transaction
import re
from django.conf import settings
#from bs4 import BeautifulSoup
from django.utils.dateparse import parse_datetime
from datetime import *
from django.utils.timezone import make_aware
from rest_framework.response import Response
import logging
import zipfile
from django.conf import settings
import boto3
import uuid
from tempfile import NamedTemporaryFile
import os
from concurrent.futures import ThreadPoolExecutor
from docx import Document
import re
logger = logging.getLogger(__name__)



class WordFileProcessorView(APIView):
    permission_classes = [AllowAny]

    def extract_questions_from_docx(self, docx_file):
        document = Document(docx_file)
        questions = []
        current_question = None
        key_answers = []
        question_counter = 0

        for paragraph in document.paragraphs:
            text = paragraph.text.strip()

            # Yangi savolni boshlash
            if text and text[0].isdigit() and '.' in text:
                if current_question:
                    questions.append(current_question)
                question_counter += 1
                current_question = {
                    "text": text,
                    "options": "",
                    "true_answer": None,
                }

            # Variantlarni qo‘shish
            elif text.startswith(("A)", "B)", "C)", "D)")) and current_question:
                current_question["options"] += text + '\n'

            # Javoblarni topish ("KEY" qismi bo'lsa)
            elif "KEY" in text.upper():
                matches = re.findall(r'(\d+)-([A-D])', text)
                key_answers = [match[1] for match in sorted(matches, key=lambda x: int(x[0]))]

        if current_question:
            questions.append(current_question)

        # "KEY"dagi javoblarni savollarga biriktirish
        for i, question in enumerate(questions):
            if i < len(key_answers):
                question["true_answer"] = key_answers[i]

        return questions

    def post(self, request, *args, **kwargs):
        """
        POST metodi Word fayldan savollarni o'qib, kategoriya va fan bilan birga ma'lumotlar bazasiga saqlaydi.
        """
        word_file = request.FILES.get('file')
        category = request.data.get('category')
        subject = request.data.get('subject')

        # Tekshirish
        if not word_file:
            return Response({"error": "Word fayl topilmadi"}, status=400)

        if not category or not subject:
            return Response({"error": "Category va Subject maydonlari majburiy."}, status=400)

        # Fayldan savollarni ajratib olish
        questions = self.extract_questions_from_docx(word_file)

        # Savollarni ma'lumotlar bazasiga saqlash
        for question in questions:
            Zip.objects.create(
                text=question["text"],
                options=question["options"],
                true_answer=question["true_answer"],
                category=category,
                subject=subject,
            )

        return Response({
            "message": f"{len(questions)} ta savol muvaffaqiyatli qayta ishlangan!",
            "category": category,
            "subject": subject,
            "data": questions
        }, status=201)




    def upload_image_to_s3(self, image_name, image_data):
            s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME

            file_name, file_extension = os.path.splitext(image_name)
            unique_name = file_name
            s3_key = f"images/{unique_name}{file_extension}"

            while self.check_file_exists_in_s3(s3_client, bucket_name, s3_key):
                unique_name = f"{uuid.uuid4().hex}{file_extension}"
                s3_key = f'images/{unique_name}'

            with NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(image_data)
                temp_file.close()
                s3_client.upload_file(temp_file.name, bucket_name, s3_key,  ExtraArgs={"ACL": "public-read"})
                os.unlink(temp_file.name)

            return f'https://{bucket_name}.s3.amazonaws.com/{s3_key}'

    def upload_images_concurrently(self, images):
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self.upload_image_to_s3, img_name, img_data): img_name for img_name, img_data in images.items()}
            return {future.result(): images[future] for future in futures}
    def check_file_exists_in_s3(self, s3_client, bucket_name, s3_key):
        try:
            s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            return True
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                raise


class FilterQuestionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        id_list = request.query_params.getlist(
            "id"
        )  # Idlarni ro'yxat ko'rinishida olish
        category = request.query_params.get("category")
        subject = request.query_params.get("subject")
        date = request.query_params.get("date")

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
                    return Response(
                        {"error": "Invalid date format. Use ISO 8601 format."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ZipSerializer(questions, many=True)
        return Response({"questions": serializer.data}, status=status.HTTP_200_OK)


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


# class QuestionPagination(PageNumberPagination):
#     page_size = 100 
#     page_size_query_param = 'limit'  
#     max_page_size = 1000  

class GenerateRandomQuestionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            list_id = request.query_params.get('list_id', None)
            question_class = request.query_params.get('question_class', None)
            date = request.query_params.get('date', None)
            question_filter = request.query_params.get('question_filter', '').lower() == 'true'
            questions_only = request.query_params.get('questions_only', '').lower() == 'true'

            # Filtrlash
            question_lists = QuestionList.objects.prefetch_related('questions').all()

            if list_id:
                question_lists = question_lists.filter(list_id=list_id)

            if question_class:
                question_lists = question_lists.filter(question_class=question_class)

            if date:
                try:
                    naive_date_time = datetime.strptime(date, "%Y-%m-%d")
                    date_time = make_aware(naive_date_time)
                    question_lists = question_lists.filter(
                        created_at__date=date_time.date()
                    )
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use YYYY-MM-DD."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Paginationni olib tashlash va ma'lumotlarni to'g'ridan-to'g'ri tayyorlash
            response_data = []
            for question_list in question_lists:
                categories = list(
                    question_list.questions.values_list(
                        "category", flat=True
                    ).distinct()
                )
                subjects = list(
                    question_list.questions.values_list("subject", flat=True).distinct()
                )

                list_data = {
                    "list_id": question_list.list_id,
                    "question_class": question_list.question_class,
                    "created_at": question_list.created_at,
                }

                if question_filter:
                    list_data["questions"] = [
                        {
                            "id": q.id,
                            "category": q.category,
                            "subject": q.subject,
                            "text": q.text,
                            "options": q.options,
                            "true_answer": q.true_answer,
                            "list": q.list_id,
                            "order": idx,
                        }
                        for idx, q in enumerate(question_list.questions.all(), start=1)
                    ]
                elif questions_only:
                    list_data["categories"] = categories
                    list_data["subjects"] = subjects
                else:
                    list_data["categories"] = categories
                    list_data["subjects"] = subjects
                    list_data["questions"] = [
                        {
                            "id": q.id,
                            "category": q.category,
                            "subject": q.subject,
                            "text": q.text,
                            "options": q.options,
                            "true_answer": q.true_answer,
                            "list": q.list_id,
                            "order": idx,
                        }
                        for idx, q in enumerate(question_list.questions.all(), start=1)
                    ]

                response_data.append(list_data)

            # To'g'ridan-to'g'ri javobni qaytarish
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)




    def post(self, request):
        try:
        # Ma'lumotni olish
            if isinstance(request.data, list):
                request_data = request.data[0]
            else:
                request_data = request.data

            questions_num = request_data.get("num", {})
            questions_data = request_data.get("data", {})
            additional_value = questions_num.get("additional_value", 0)
            question_class = questions_num.get("class", "")

            majburiy_fan_1 = questions_data.get("Majburiy_Fan_1", [])
            majburiy_fan_2 = questions_data.get("Majburiy_Fan_2", [])
            majburiy_fan_3 = questions_data.get("Majburiy_Fan_3", [])
            fan_1 = questions_data.get("Fan_1", [])
            fan_2 = questions_data.get("Fan_2", [])

            final_lists = []

            for _ in range(additional_value):
                new_list = {
                    "Majburiy_Fan_1": self.get_random_items(majburiy_fan_1, 10),
                    "Majburiy_Fan_2": self.get_random_items(majburiy_fan_2, 10),
                    "Majburiy_Fan_3": self.get_random_items(majburiy_fan_3, 10),
                    "Fan_1": self.get_random_items(fan_1, 30),
                    "Fan_2": self.get_random_items(fan_2, 30),
                }

            # Bazadan oxirgi `list_id` ni olish
                last_list = QuestionList.objects.order_by("-list_id").first()
                list_id = (last_list.list_id + 1) if last_list else 100000

                final_questions = {category: [] for category in new_list.keys()}
                global_order_counter = 1

                for category, questions in new_list.items():
                    for question in questions:
                        final_questions[category].append(
                            {
                                "category": category,
                                "subject": question.get("subject", ""),
                                "text": question.get("text", ""),
                                "options": question.get("options", ""),
                                "true_answer": question.get("true_answer", ""),
                                "image": question.get("image", None),
                                "order": global_order_counter,
                            }
                        )
                        global_order_counter += 1

                final_lists.append(
                    {
                        "list_id": list_id,
                        "questions": final_questions,
                        "question_class": question_class,
                    }
                )

                try:
                    with transaction.atomic():
                        question_list = QuestionList.objects.create(
                        list_id=list_id, question_class=question_class
                        )
                        for category, questions in final_questions.items():
                            for question in questions:
                                Question.objects.create(
                                    list=question_list,
                                    category=category,
                                    subject=question.get("subject", ""),
                                    text=question.get("text", ""),
                                    options=question.get("options", ""),
                                    true_answer=question.get("true_answer", ""),
                                    order=question.get("order", 0),
                                )
                except Exception as e:
                    print(f"Error during database save: {e}")
                    return Response(
                        {"error": "Database save error"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            return Response(
                {"success": "Questions saved successfully", "data": final_lists},
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @staticmethod
    def get_random_items(source_list, count):
        if not source_list:
            return []
        count = min(count, len(source_list))
        return random.sample(source_list, count)

