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
import uuid
from concurrent.futures import ThreadPoolExecutor
from tempfile import NamedTemporaryFile
import os
logger = logging.getLogger(__name__)


class HTMLFromZipView(APIView):
    permission_classes = [AllowAny]

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

    def clean_img_tag(self, img_tag, new_src):
        img_tag.attrs = {'src': new_src}
    
    def process_html_task(self, html_file, images, category, subject):
        soup = BeautifulSoup(html_file, 'html.parser')
        questions = []
        current_question = None

        image_urls = {}
        for image_name, image_data in images.items():
            try:
                uploaded_url = self.upload_image_to_s3(image_name, image_data)
                image_urls[image_name] = uploaded_url
            except Exception as e:
                print(f"Error uploading {image_name}: {e}")

        # <img> teglarini tozalash va yangilash
        for img_tag in soup.find_all('img'):
            img_src = img_tag.get('src')
            if img_src and img_src in image_urls:
                self.clean_img_tag(img_tag, image_urls[img_src])
            else:
                img_tag.decompose()  # <img> tegi bucketga yuklanmagan bo'lsa, o'chiramiz

        # "KEY" bo‘limini topish va true_answerlarni ajratib olish
        key_answers = []
        for p_tag in soup.find_all('p'):
            if "KEY" in p_tag.get_text(strip=True).upper():
                key_text = p_tag.get_text(strip=True)
                matches = re.findall(r'(\d+)-([A-D])', key_text)
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
                current_question["options"] += str(p_tag)  # Variantlarni tozalash

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




    def upload_image_to_s3(self, image_name, image_data):
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        s3_key = f"pdf_image/{uuid.uuid4().hex}.jpg"

        try:
            with NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(image_data)
                temp_file.close()

            # Faylni yuklash
                s3_client.upload_file(
                    temp_file.name,
                    bucket_name,
                    s3_key,
                    ExtraArgs={"ACL": "public-read"}
                )

            # Vaqtinchalik faylni o‘chirish
                os.unlink(temp_file.name)

        # Fayl URL-ni qaytarish
            return f'https://{bucket_name}.s3.amazonaws.com/{s3_key}'
        except Exception as e:
            print(f"Error uploading {image_name}: {e}")
            raise


    def upload_images_concurrently(self, images):
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self.upload_image_to_s3, img_name, img_data)
                for img_name, img_data in images.items()
            ]
            return [future.result() for future in futures]

          
    def check_file_exists_in_s3(self, s3_client, bucket_name, s3_key):
        try:
            s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            return True
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                raise




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
                    # Faqat yil, oy va kunni olish uchun datetime yaratish
                    filter_date = datetime.strptime(date, "%Y-%m-%d").date()
                    question_lists = question_lists.filter(created_at__date=filter_date)
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


