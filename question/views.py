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
from bs4 import BeautifulSoup
import zipfile
from django.utils.dateparse import parse_datetime
from datetime import *
from django.utils.timezone import make_aware
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
import logging
import zipfile
from django.conf import settings
import boto3
import uuid
from tempfile import NamedTemporaryFile
import os
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
class HTMLFromZipView(APIView):
    
    def process_html_task(self, html_file, images, category, subject):
        soup = BeautifulSoup(html_file, 'html.parser')
        questions = []
        current_question = None

    # Rasmlarni S3 bucketga yuklash va URLni yangilash
        image_urls = {image_name: self.upload_image_to_s3(image_name, image_data) for image_name, image_data in images.items()}

        for img_tag in soup.find_all('img'):
            img_src = img_tag.get('src')
            if img_src in image_urls:
                img_tag['src'] = image_urls[img_src]
            else:
                img_tag.decompose()

    # "KEY" bo‘limini topish va true_answerlarni ajratib olish
        key_answers = []
        for p_tag in soup.find_all('p'):
            if "KEY" in p_tag.get_text(strip=True).upper():
                key_text = p_tag.get_text(strip=True)
                matches = re.findall(r'(\d+)-([A-D])', key_text)  # Masalan: 1-A, 2-B kabi formatni olish
                key_answers = [match[1] for match in sorted(matches, key=lambda x: int(x[0]))]
                break

    # Savollarni ajratib olish
        question_counter = 0
        for p_tag in soup.find_all('p'):
            text = p_tag.get_text(strip=True)
            if not text:
                continue

        # Yangi savolni boshlash
            if text[0].isdigit() and '.' in text:
                if current_question:
                    questions.append(current_question)
                question_counter += 1
                current_question = {
                    "text": str(p_tag),
                    "options": "",
                    "true_answer": None,
                    "category": category,
                    "subject": subject
                }

        # Variantlarni qo‘shish
            elif text.startswith(("A)", "B)", "C)", "D)")) and current_question:
                current_question["options"] += str(p_tag)

        if current_question:
            questions.append(current_question)

    # "KEY"dagi javoblarni savollarga biriktirish
        for i, question in enumerate(questions):
            if i < len(key_answers):
                question["true_answer"] = key_answers[i]

    # Ma'lumotlarni saqlash
        for question in questions:
            Zip.objects.create(
                text=question["text"],
                options=question["options"],
                true_answer=question["true_answer"],
                category=question["category"],
                subject=question["subject"]
            )

        return f"{len(questions)} ta savol muvaffaqiyatli qayta ishlangan!"
    


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
                s3_client.upload_file(temp_file.name, bucket_name, s3_key)
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

    def post(self, request, *args, **kwargs):
        zip_file = request.FILES.get('file')
        if not zip_file:
            return Response({"error": "ZIP fayl topilmadi"}, status=400)

        category = request.data.get('category')
        subject = request.data.get('subject')

        if not category or not subject:
            return Response(
                {"error": "Category va Subject majburiy maydonlardir."},
                status=400
            )

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

            questions = self.process_html_task(html_file, images, category, subject)


        return Response({"message": "Savollarni Yuklash Jarayoni Tugatildi"}, status=201)

        
    def get(self, request, *args, **kwargs):
        questions = Zip.objects.all()
        result = []

        for question in questions:
            question_data = {
                "text": question.text,
                "options": question.options,
                "true_answer": question.true_answer,
                "category": question.category,
                "subject": question.subject
            }

            soup = BeautifulSoup(question.text, 'html.parser')
            for img_tag in soup.find_all('img'):
                img_src = img_tag.get('src')
                if img_src and img_src.startswith('images/'):
                    img_tag['src'] = f'https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{img_src}'

            question_data["text"] = str(soup)
            result.append(question_data)

        return Response(result, status=200)



class FilterQuestionsView(APIView):
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
    def delete(self, request):
        Zip.objects.all().delete()
        return Response(
            {"message": "All questions have been deleted successfully."},
            status=status.HTTP_200_OK,
        )


class QuestionPagination(PageNumberPagination):
    page_size = 100 
    page_size_query_param = 'limit'  
    max_page_size = 1000  


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

            # Paginationni qo'llash
            paginator = QuestionPagination()
            paginated_lists = paginator.paginate_queryset(question_lists, request)

            # Javob uchun ma'lumotlarni tayyorlash
            response_data = []
            for question_list in paginated_lists:
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

            # Paginated javobni qaytarish
            return paginator.get_paginated_response(response_data)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        try:
            if isinstance(request.data, list):
                request_data = request.data[0]
            else:
                request_data = request.data

            questions_num = request_data.get("num", {})
            questions_data = request_data.get("data", {})
            additional_value = questions_num.get("additional_value")
            question_class = questions_num.get("class", "")

            majburiy_fan_1 = questions_data.get("Majburiy_Fan_1", [])
            majburiy_fan_2 = questions_data.get("Majburiy_Fan_2", [])
            majburiy_fan_3 = questions_data.get("Majburiy_Fan_3", [])
            fan_1 = questions_data.get("Fan_1", [])
            fan_2 = questions_data.get("Fan_2", [])

            final_lists = []

            for _ in range(additional_value):
                new_list = {
                    "Majburiy_Fan_1": self.clean_questions(
                        self.get_random_items(majburiy_fan_1, 10)
                    ),
                    "Majburiy_Fan_2": self.clean_questions(
                        self.get_random_items(majburiy_fan_2, 10)
                    ),
                    "Majburiy_Fan_3": self.clean_questions(
                        self.get_random_items(majburiy_fan_3, 10)
                    ),
                    "Fan_1": self.clean_questions(self.get_random_items(fan_1, 30)),
                    "Fan_2": self.clean_questions(self.get_random_items(fan_2, 30)),
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
                                "subject": self.strip_html_tags(
                                    question.get("subject", "")
                                ),
                                "text": self.strip_html_tags(question["text"]),
                                "options": self.strip_html_tags(
                                    question.get("options", "")
                                ),
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

            return Response(status=status.HTTP_201_CREATED)

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

    @staticmethod
    def clean_questions(questions):
        for question in questions:
            question["text"] = re.sub(r"^\d+\.\s*", "", question["text"])
        return questions

    @staticmethod
    def strip_html_tags(html_content):
        if not html_content:
            return ""

        def preserve_img_tag(match):
            tag = match.group(0)
            if tag.startswith("<img") and "src=" in tag:
                src_match = re.search(r'src="([^"]+)"', tag)
                if src_match:
                    return src_match.group(1)
            return ""

        html_without_tags = re.sub(r"<[^>]+>", preserve_img_tag, html_content)
        return html_without_tags.strip()
