from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import QuestionList, Question, Zip
from .serializers import ZipSerializer
from rest_framework.permissions import AllowAny
import random
from django.db import transaction
from django.utils.dateparse import parse_datetime
from datetime import *
from rest_framework.response import Response
import logging
from django.conf import settings
import re
import fitz
import tempfile
import boto3
import uuid
from concurrent.futures import ThreadPoolExecutor
from tempfile import NamedTemporaryFile
import os
logger = logging.getLogger(__name__)



class PDFUploadView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        """Barcha PDF fayllar tarkibini qaytarish"""
        questions = Zip.objects.all()
        result = []

        for question in questions:
            pdf_path = question.text  # `text` maydonida PDF fayl manzili saqlangan deb hisoblaymiz
            if not os.path.exists(pdf_path):
                continue  # Agar fayl mavjud bo'lmasa, uni o'tkazib yuboramiz

            pdf_content = self.extract_pdf_content(pdf_path)
            result.append({
                "category": question.category,
                "subject": question.subject,
                "pdf_content": pdf_content
            })

        return Response(result, status=200)

    def extract_images_from_pdf(self, pdf_file):
        """PDF fayldan barcha rasmlarni chiqarib, S3 ga yuklash"""
        doc = fitz.open(pdf_file)
        image_urls = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            images = page.get_images(full=True)

            for img_index, img in enumerate(images):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_data = base_image["image"]

            # Fayl nomini generatsiya qilish (UUID ishlatilmoqda)
                unique_image_name = f"{uuid.uuid4()}.jpg"

                try:
                    uploaded_url = self.upload_image_to_s3(unique_image_name, image_data)
                    image_urls.append(uploaded_url)
                except Exception as e:
                    print(f"Error uploading image: {e}")

    def post(self, request, *args, **kwargs):
        pdf_file = request.FILES.get('file')
        if not pdf_file:
            return Response({"error": "PDF fayl topilmadi."}, status=400)

    # Vaqtinchalik PDF fayl yaratish
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                temp_pdf.write(pdf_file.read())
                temp_pdf_path = temp_pdf.name
        except Exception as e:
            return Response({"error": f"Vaqtinchalik fayl yaratishda xatolik: {str(e)}"}, status=500)

        try:
        # PDF dan rasmlarni chiqarish
            image_urls = self.extract_images_from_pdf(temp_pdf_path)
        except Exception as e:
            return Response({"error": f"PDFdan rasm chiqarishda xatolik: {str(e)}"}, status=500)
        finally:
        # Faylni faqat mavjud bo‘lsa o‘chirish
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)

        if not image_urls:
            return Response({"message": "PDF faylda rasm topilmadi."}, status=204)

        return Response({"image_urls": image_urls}, status=201)



    def upload_image_to_s3(self, image_name, image_data):
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    # Fayl nomini unikal qilish
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

