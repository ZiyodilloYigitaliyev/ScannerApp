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
from tempfile import NamedTemporaryFile
from rest_framework.parsers import MultiPartParser, FormParser
import boto3
from bs4 import BeautifulSoup
import zipfile
import os
from django.utils.dateparse import parse_datetime
from datetime import *
from django.db.models import Max
from django.utils.timezone import make_aware


class HTMLFromZipView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def find_red_class(self, soup):
        style_tags = soup.find_all("style")
        red_classes = []

        for style_tag in style_tags:
            styles = style_tag.string
            if styles:
                matches = re.findall(
                    r'\.(\w+)\s*{[^}]*color:\s*(#ff0000|rgb\(255,\s*0,\s*0\)|rgba\(255,\s*0,\s*0,\s*[\d\.]+\))\s*;?',
                    styles,
                    re.IGNORECASE
                )
                red_classes.extend([match[0] for match in matches])
        return red_classes

    def extract_true_answer(self, p_tag, red_classes):

        for span_tag in p_tag.find_all("span"):
            span_classes = span_tag.get("class", [])
            if any(cls in red_classes for cls in span_classes):
                return span_tag.text.strip()
        return None

    def upload_image_to_s3(self, image_name, image_data):
        """
        Rasmlarni S3 bucketga yuklash va URLni qaytarish.
        """
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        temp_file = NamedTemporaryFile(delete=False)
        temp_file.write(image_data)
        temp_file.close()
        s3_key = f'images/{os.path.basename(image_name)}'
        s3_client.upload_file(temp_file.name, bucket_name, s3_key)
        os.unlink(temp_file.name)
        return f'https://{bucket_name}.s3.amazonaws.com/{s3_key}'

    def process_html(self, html_file, images, category, subject):
        """
        HTML faylni qayta ishlash va savollarni ajratib olish.
        """
        soup = BeautifulSoup(html_file, 'html.parser')
        red_class = self.find_red_class(soup)
        image_urls = {img_name: self.upload_image_to_s3(img_name, img_data) for img_name, img_data in images.items()}

        # Rasmlarning `src` atributlarini yangilash
        for img_tag in soup.find_all('img'):
            img_src = img_tag.get('src')
            if img_src in image_urls:
                img_tag['src'] = image_urls[img_src]

        # Savollarni ajratib olish
        questions = []
        current_question = None

        for p_tag in soup.find_all('p'):
            text = p_tag.get_text(strip=True)
            if not text:
                continue

            # Yangi savolni boshlash
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
            # Variantlarni qo'shish
            elif text.startswith(("A)", "B)", "C)", "D)")) and current_question:
                current_question["options"] += str(p_tag)

                # To'g'ri javobni aniqlash
                if red_class:
                    for span_tag in p_tag.find_all("span", class_=red_class):
                        answer_text = span_tag.get_text(strip=True)
                        if answer_text.startswith(("A", "B", "C", "D")):
                            current_question["true_answer"] = answer_text[0]

        # Oxirgi savolni qo'shish
        if current_question:
            questions.append(current_question)

        return questions

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

        # HTMLni qayta ishlash
        questions = self.process_html(html_file, images, category, subject)

        # Ma'lumotlar bazasiga saqlash
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
            question_class = request.query_params.get('question_class', None)
            limit = request.query_params.get('limit', None)
            date = request.query_params.get('date', None)
            question_filter = request.query_params.get('question_filter', '').lower() == 'true'
            questions_only = request.query_params.get('questions_only', '').lower() == 'true'

            if question_filter and questions_only:
                return Response(
                    {"error": "You cannot use 'question_filter' and 'questions_only' at the same time."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Barcha question_lists ma'lumotlarini olish
            question_lists = QuestionList.objects.prefetch_related('questions').all()

            # list_id bo'yicha filter
            if list_id:
                question_lists = question_lists.filter(list_id=list_id)

            # questions_class bo'yicha filter
            if question_class:
                question_lists = question_lists.filter(question_class=question_class)

            # date bo'yicha filter
            if date:
                try:
                    naive_date_time = datetime.strptime(date, "%Y-%m-%d")
                    date_time = make_aware(naive_date_time)
                    question_lists = question_lists.filter(created_at__date=date_time.date())
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use YYYY-MM-DD."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Limitni qo'llash
            if limit:
                try:
                    limit = int(limit)
                    question_lists = question_lists[:limit]
                except ValueError:
                    return Response({"error": "Invalid limit value. It should be an integer."},
                                    status=status.HTTP_400_BAD_REQUEST)

            # Ma'lumotlarni tayyorlash
            response_data = []
            for question_list in question_lists:
                # Har xil category va subject qiymatlarini olish
                categories = list(question_list.questions.values_list("category", flat=True).distinct())
                subjects = list(question_list.questions.values_list("subject", flat=True).distinct())

                # Natija uchun ma'lumotlarni tayyorlash
                list_data = {
                    "list_id": question_list.list_id,
                    "question_class": question_list.question_class,
                    "created_at": question_list.created_at,
                }

                # Filterga ko'ra ma'lumotlarni tayyorlash
                if question_filter and question_filter.lower() == "true":
                    # Faqat `questions`ni qo'shish
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
                elif questions_only and questions_only.lower() == "true":
                    # Faqat `categories` va `subjects`ni qo'shish
                    list_data["categories"] = categories
                    list_data["subjects"] = subjects
                else:
                    # Default holat: barcha ma'lumotlarni qo'shish
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
                return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        try:
            if isinstance(request.data, list):
                request_data = request.data[0]
            else:
                request_data = request.data

            questions_num = request_data.get('num', {})
            questions_data = request_data.get('data', {})
            additional_value = questions_num.get('additional_value')
            question_class = questions_num.get('class', '')

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

                # Bazadan oxirgi `list_id` ni olish
                last_list = QuestionList.objects.order_by('-list_id').first()
                list_id = (last_list.list_id + 1) if last_list else 100000

                final_questions = {category: [] for category in new_list.keys()}
                global_order_counter = 1

                for category, questions in new_list.items():
                    for question in questions:
                        final_questions[category].append({
                            "category": category,
                            "subject": self.strip_html_tags(question.get("subject", "")),
                            "text": self.strip_html_tags(question["text"]),
                            "options": self.strip_html_tags(question.get("options", "")),
                            "true_answer": question.get("true_answer", ""),
                            "image": question.get("image", None),
                            "order": global_order_counter,
                        })
                        global_order_counter += 1

                final_lists.append({
                    "list_id": list_id,
                    "questions": final_questions,
                    "question_class": question_class
                })

                try:
                    with transaction.atomic():
                        question_list = QuestionList.objects.create(list_id=list_id, question_class=question_class)
                        for category, questions in final_questions.items():
                            for question in questions:
                                Question.objects.create(
                                    list=question_list,
                                    category=category,
                                    subject=question.get('subject', ""),
                                    text=question.get('text', ""),
                                    options=question.get('options', ""),
                                    true_answer=question.get('true_answer', ""),
                                    order=question.get('order', 0),
                                )
                except Exception as e:
                    print(f"Error during database save: {e}")
                    return Response({"error": "Database save error"}, status=status.HTTP_400_BAD_REQUEST)

            return Response(status=status.HTTP_201_CREATED)

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

    @staticmethod
    def strip_html_tags(html_content):
        if not html_content:
            return ""

        # img teglari va ulardagi src atributlarini saqlab qolish
        def preserve_img_tag(match):
            tag = match.group(0)
            # Agar tag img bo'lsa, faqat src qiymatini saqlash
            if tag.startswith('<img') and 'src=' in tag:
                src_match = re.search(r'src="([^"]+)"', tag)
                if src_match:
                    return src_match.group(1)  # src qiymatini qaytaradi
            return ''  # Boshqa hollarda tegni olib tashlaydi

        # HTML teglarini filtr qilish
        html_without_tags = re.sub(r'<[^>]+>', preserve_img_tag, html_content)
        return html_without_tags.strip()