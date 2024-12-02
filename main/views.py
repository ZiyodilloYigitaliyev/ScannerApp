import zipfile
from io import BytesIO
import boto3
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import UploadedFile
import os
from django.conf import settings
from .models import *
from docx import Document
from django.core.files.base import ContentFile
from PIL import Image
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.storage import default_storage
import docx
from .serializers import QuestionSerializer
class UploadZipView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            # ZIP faylini olish
            file = request.FILES['file']
            zip_file = zipfile.ZipFile(file)

            # Boto3 clientini sozlash
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION_NAME
            )

            uploaded_files = []

            # ZIP faylidan PDF fayllarini chiqarib olish
            for name in zip_file.namelist():
                if name.endswith(".pdf"):
                    # Faqat fayl nomini olish (papka tuzilmalarini tashlab yuborish)
                    file_name = os.path.basename(name)

                    # Faylni ochish
                    pdf_file = zip_file.open(name)
                    file_content = pdf_file.read()

                    # Faylni S3'ga yuklash
                    s3_path = f"pdf_files/{file_name}"  # Papkalarni olib tashlaymiz
                    s3_client.put_object(
                        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                        Key=s3_path,
                        Body=file_content,
                        ContentType='application/pdf',
                        ACL='public-read'  # Faylga public-read ruxsatini o'rnatish
                    )

                    # Faylga ommaviy URL yaratish
                    uploaded_file_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{s3_path}"
                    uploaded_files.append(uploaded_file_url)

                    # Ma'lumotni bazaga saqlash
                    UploadedFile.objects.create(name=file_name, s3_url=uploaded_file_url)

            return Response(
                {"success": "true", "message": "Files uploaded successfully!", "uploaded_files": uploaded_files},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response({"success": "false", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class UploadQuestionsView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'Fayl topilmadi'}, status=400)

        # Faylni vaqtinchalik saqlash
        file_path = default_storage.save(f'temp/{file.name}', file)

        try:
            # Word faylni ochish
            doc = docx.Document(file_path)
            questions = []  # Yig'ilgan savollar ro'yxati

            question_text = None
            answers = []
            correct_answer = None
            question_images = []  # Rasmlar uchun

            for para in doc.paragraphs:
                text = para.text.strip()

                # Rasmni ajratib olish
                if para.runs and para.runs[0].element.xpath('.//w:drawing'):
                    question_images.append(para.runs[0].element)

                if not text:
                    continue  # Bo'sh qatorlarni o'tkazib yuborish

                if text[0].isdigit() and '.' in text:  # Savol boshlandi
                    # Oldingi savolni saqlash
                    if question_text and correct_answer and len(answers) == 4:
                        questions.append(
                            Question(
                                text=question_text,
                                correct_answer=correct_answer,
                                answerA=answers[0]['text'],
                                answerB=answers[1]['text'],
                                answerC=answers[2]['text'],
                                answerD=answers[3]['text'],
                            )
                        )
                        question_images.clear()  # Har bir savol uchun rasmlar qayta boshlanadi

                    # Yangi savolni boshlash
                    question_text = text.split('.', 1)[1].strip()
                    answers = []
                    correct_answer = None

                elif text[0] in 'ABCD':  # Javob variantlari
                    answer_letter = text[0]
                    if answer_letter.islower():
                        continue  # Kichik harfli javoblarni e'tiborsiz qoldirish

                    answer_text = text[2:].strip()[:10]  # Javobni 10 belgidan oshirmaslik
                    for run in para.runs:
                        if run.font.color and run.font.color.rgb == docx.shared.RGBColor(255, 0, 0):
                            correct_answer = answer_letter

                    answers.append({'letter': answer_letter, 'text': answer_text})

            # Oxirgi savolni saqlash
            if question_text and correct_answer and len(answers) == 4:
                questions.append(
                    Question(
                        text=question_text,
                        correct_answer=correct_answer,
                        answerA=answers[0]['text'],
                        answerB=answers[1]['text'],
                        answerC=answers[2]['text'],
                        answerD=answers[3]['text'],
                    )
                )

            # Savollarni 10 tadan bo'lib saqlash
            chunk_size = 10
            for i in range(0, len(questions), chunk_size):
                Question.objects.bulk_create(questions[i:i + chunk_size])

            return Response({'message': 'Savollar muvaffaqiyatli yuklandi!', 'count': len(questions)}, status=201)

        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            # Vaqtinchalik faylni o'chirish
            default_storage.delete(file_path)