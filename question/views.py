import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from sympy import Max
from .models import QuestionList, Question, Zip, Backup
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
    
    EXTERNAL_POST_URL = "https://scan-app-9206bf041b06.herokuapp.com/savol/backup/"

    def get(self, request):
        try:
            list_id = request.query_params.get('list_id', None)
            question_class = request.query_params.get('question_class', None)
            date = request.query_params.get('date', None)
            category = request.query_params.get('category', None)
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
                    filter_date = datetime.strptime(date, "%Y-%m-%d").date()
                    question_lists = question_lists.filter(created_at__date=filter_date)
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use YYYY-MM-DD."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            response_data = []
            for question_list in question_lists:
                # Kategoriyalarni belgilangan tartibda olish
                category_order = [
                    "Majburiy_Fan_1",
                    "Majburiy_Fan_2",
                    "Majburiy_Fan_3",
                    "Fan_1",
                    "Fan_2"
                ]
                
                # Savollarni kategoriyalar bo'yicha guruhlash
                all_questions = question_list.questions.all()
                if category:
                    all_questions = all_questions.filter(category=category)

                grouped_questions = {}
                for q in all_questions:
                    grouped_questions.setdefault(q.category, []).append(q)

                # Kategoriyalarni tartiblash va savollarni randomlashtirish
                ordered_questions = []
                for cat in category_order:
                    if cat in grouped_questions:
                        random.shuffle(grouped_questions[cat])  # Kategoriya ichida random
                        ordered_questions.extend(grouped_questions[cat])

                # Global orderni yaratish
                final_questions = [
                    {
                        "id": q.id,
                        "category": q.category,
                        "text": q.text,
                        "options": q.options,
                        "subject": q.subject,
                        "true_answer": q.true_answer,
                        "list": q.list_id,
                        "order": idx + 1  # 1 dan boshlab tartib
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

            # Kategoriyalarni tartibi saqlanadigan qilib olish
            category_structure = {
                "Majburiy_Fan_1": questions_data.get("Majburiy_Fan_1", []),
                "Majburiy_Fan_2": questions_data.get("Majburiy_Fan_2", []),
                "Majburiy_Fan_3": questions_data.get("Majburiy_Fan_3", []),
                "Fan_1": questions_data.get("Fan_1", []),
                "Fan_2": questions_data.get("Fan_2", []),
            }

            final_lists = []

            for _ in range(additional_value):
                # Bazadan oxirgi `list_id` ni olish
                last_list = QuestionList.objects.order_by("-list_id").first()
                list_id = (last_list.list_id + 1) if last_list else 100000

                final_questions = []

                # Har bir kategoriya uchun random savollarni olish (kategoriya tartibini buzmaslik)
                for category in category_structure.keys():
                    questions = category_structure[category]
                    if not questions:
                        continue  # Bo'sh kategoriya bo‘lsa tashlab ketamiz
                    
                    random_questions = self.get_random_items(questions, 10 if "Majburiy" in category else 30)

                    # Kategoriya ichidagi savollarni tartib bilan qo‘shish
                    for idx, q in enumerate(random_questions):
                        final_questions.append({
                            "category": category,
                            "subject": q.get("subject", ""),
                            "text": q.get("text", ""),
                            "options": q.get("options", ""),
                            "true_answer": q.get("true_answer", ""),
                            "order": idx + 1,  # **Kategoriya ichida tartibni saqlash**
                        })

                final_lists.append(
                    {
                        "list_id": list_id,
                        "questions": final_questions,  # **Kategoriya tartibini saqlagan holda APIga chiqadi**
                        "question_class": question_class,
                    }
                )

                # Bazaga saqlash
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
                    print(f"Error during database save: {e}")
                    return Response(
                        {"error": "Database save error"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Barcha ma'lumotlar muvaffaqiyatli saqlandi, endi avtomatik tashqi urlga post qilamiz
            self._auto_post_saved_data()

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
                # O'chirilishi kerak bo'lgan modelni tanlang
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
    
    def _auto_post_saved_data(self):
        try:
            # Barcha QuestionList va ular bilan bog'liq savollarni olish
            question_lists = QuestionList.objects.prefetch_related('questions').all()
            payload = []

            for question_list in question_lists:
                questions_data = []
                for q in question_list.questions.all():
                    questions_data.append({
                        "id": q.id,
                        "category": q.category,
                        "subject": q.subject,
                        "text": q.text,
                        "options": q.options,
                        "true_answer": q.true_answer,
                        "order": q.order,
                    })
                payload.append({
                    "list_id": question_list.list_id,
                    "question_class": question_list.question_class,
                    "created_at": question_list.created_at.isoformat(),
                    "questions": questions_data,
                })

            response = requests.post(self.EXTERNAL_POST_URL, json=payload)
            response.raise_for_status()  # Xatolik yuz bersa exception ko'tariladi
            print("Auto post successful. Response status:", response.status_code)
        except Exception as e:
            print("Failed to auto-post data to external url:", e)



class BackupDataView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            backups = Backup.objects.all()
            data = []
            for backup in backups:
                data.append({
                    "list_id": backup.list_id,
                    "category": backup.category,
                    "subject": backup.subject,
                    "text": backup.text,
                    "options": backup.options,
                    "true_answer": backup.true_answer,
                    "order": backup.order,
                })
            return Response({"data": data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Xatolik yuz berdi: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    def post(self, request, *args, **kwargs):
        try:
            incoming_data = request.data

            # Agar ma'lumot yagona obyekt sifatida kelsa, uni ro'yxatga o'ramiz
            if isinstance(incoming_data, dict):
                data_list = [incoming_data]
            elif isinstance(incoming_data, list):
                data_list = incoming_data
            else:
                return Response(
                    {"error": "Ma'lumot dictionary yoki ro'yxat shaklida yuborilishi kerak."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            backups_saved = []
            with transaction.atomic():
                for item in data_list:
                    # Ma'lumot maydonlarini olish (agar mavjud bo'lmasa, keyinchalik avtomatik qiymat beramiz)
                    orig_list_id = item.get("list_id")
                    orig_order = item.get("order")
                    category   = item.get("category", "")
                    subject    = item.get("subject", "")
                    text       = item.get("text", "")
                    options    = item.get("options", "")
                    true_answer= item.get("true_answer", "")

                    # Agar list_id yoki order kiritilmagan bo'lsa, ularni bazadagi eng katta qiymatdan birga oshirib aniqlaymiz
                    if orig_list_id is None:
                        list_id = self._get_next_value("list_id")
                    else:
                        list_id = self._get_unique_value("list_id", orig_list_id)

                    if orig_order is None:
                        order = self._get_next_value("order")
                    else:
                        order = self._get_unique_value("order", orig_order)

                    # Yangi yozuvni yaratamiz
                    backup_obj = Backup.objects.create(
                        list_id=list_id,
                        order=order,
                        category=category,
                        subject=subject,
                        text=text,
                        options=options,
                        true_answer=true_answer,
                    )
                    backups_saved.append({
                        "list_id": backup_obj.list_id,
                        "order": backup_obj.order,
                        "created": True
                    })

            return Response(
                {"success": "Backup Malumotlari Muvaffaqiyatli Saqlandi"},
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {"error": f"Xatolik yuz berdi: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _get_unique_value(self, field_name, current_value):
        filter_kwargs = {field_name: current_value}
        if Backup.objects.filter(**filter_kwargs).exists():
            max_value = Backup.objects.aggregate(max_val=Max(field_name))['max_val'] or current_value
            return max_value + 1
        else:
            return current_value

    def _get_next_value(self, field_name):
        max_value = Backup.objects.aggregate(max_val=Max(field_name))['max_val']
        return (max_value + 1) if max_value is not None else 1

    def auto_post_backup_data(self, external_url):
        try:
            backups = Backup.objects.all()
            payload = []
            for backup in backups:
                payload.append({
                    "list_id": backup.list_id,
                    "category": backup.category,
                    "subject": backup.subject,
                    "text": backup.text,
                    "options": backup.options,
                    "true_answer": backup.true_answer,
                    "order": backup.order,
                })

            headers = {'Content-Type': 'application/json'}
            response = requests.post(external_url, json=payload, headers=headers)
            response.raise_for_status()
            print("Auto post successful. Response status:", response.status_code)
        except Exception as e:
            print("Failed to auto-post data to external url:", e)