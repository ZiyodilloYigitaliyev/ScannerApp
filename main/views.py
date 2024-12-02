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
        
        # Word faylni ochish
        try:
            doc = docx.Document(file_path)
            for table in doc.tables:
                for row in table.rows:
                    question_text = row.cells[0].text.strip()  # Savol matni
                    correct_answer = None
                    answers = {'A': '', 'B': '', 'C': '', 'D': ''}

                    for i, cell in enumerate(row.cells[1:]):  # Variantlarni o'qish
                        text = cell.text.strip()
                        if text.startswith('A)') or text.startswith('B)') or text.startswith('C)') or text.startswith('D)'):
                            answer_key = text[0]  # Variant harfi (A, B, C, D)
                            answers[answer_key] = text[2:].strip()  # Variant matni

                        # Qizil rangni aniqlash
                        for run in cell.paragraphs[0].runs:
                            if run.font.color.rgb == docx.shared.RGBColor(255, 0, 0):  # Qizil rang
                                correct_answer = text[0]  # To'g'ri javob harfi (A, B, C yoki D)

                    # Modelga saqlash
                    if question_text and correct_answer:
                        Question.objects.create(
                            text=question_text,
                            correct_answer=correct_answer,
                            answerA=answers.get('A', ''),
                            answerB=answers.get('B', ''),
                            answerC=answers.get('C', ''),
                            answerD=answers.get('D', ''),
                        )
            return Response({'message': 'Savollar muvaffaqiyatli yuklandi!'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            # Vaqtinchalik faylni o'chirish
            default_storage.delete(file_path)
