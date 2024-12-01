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
from .models import Question, Answer
from docx import Document
from django.core.files.base import ContentFile
from PIL import Image
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



class UploadDocxView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            # Faylni olish
            file = request.FILES['file']
            doc = Document(file)

            # Faylni tahlil qilish
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():  # Matn bo'sh bo'lmasligi kerak
                    # Savol matnini olish
                    question_text = paragraph.text.strip()

                    # Savol va variantlarni saqlash
                    question = Question.objects.create(text=question_text, correct_answer="")

                    # Savolning javoblarini qo'shish
                    answer_choices = []  # Javob variantlari ro'yxati

                    for run in paragraph.runs:
                        # To'g'ri javobni aniqlash (qizil rangda bo'lishi kutiladi)
                        if run.font.color and run.font.color.rgb == (255, 0, 0):  # Qizil rang
                            correct_answer = run.text.strip()
                            question.correct_answer = correct_answer
                        else:
                            answer_choices.append(run.text.strip())

                    # Javoblarni bazaga saqlash
                    for answer in answer_choices:
                        is_correct = (answer == question.correct_answer)
                        Answer.objects.create(question=question, text=answer, is_correct=is_correct)

                    # Rasmlar bilan ishlash
                    for rel in doc.part.rels.values():
                        if "image" in rel.target_ref:
                            image_data = rel.target_part.blob
                            image = Image.open(BytesIO(image_data))
                            image_file = BytesIO()
                            image.save(image_file, format='PNG')
                            question.image.save(f"{question.id}.png", ContentFile(image_file.getvalue()))

            return Response({"success": True, "message": "File processed successfully."}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"success": False, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
