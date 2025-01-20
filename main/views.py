import zipfile
import os
import json
import cv2
import boto3
import numpy as np
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.db import transaction
from .serializers import ZipFileSerializer, ProcessedTestSerializer
from .models import ProcessedTest, ProcessedTestResult
from question.models import Question, QuestionList
import shutil
from rest_framework.permissions import AllowAny
import logging
from question.models import Zip

logger = logging.getLogger(__name__)
# S3 bilan ishlash uchun yordamchi funksiya
def upload_to_s3(file_path, s3_key):
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION_NAME
    )
    with open(file_path, 'rb') as f:
        s3.upload_fileobj(f, settings.AWS_STORAGE_BUCKET_NAME, s3_key)
    file_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_REGION_NAME}.amazonaws.com/{s3_key}"
    return file_url

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDINATES_PATH = os.path.join(BASE_DIR, 'app/coordinates/coordinates.json')
ID_PATH = os.path.join(BASE_DIR, 'app/coordinates/id.json')

def load_coordinates_from_json(json_path):
    with open(json_path, 'r') as file:
        return json.load(file)

def check_marked_circle(image_path, coordinates, threshold=200):
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    marked_answers = {}

    for question, options in coordinates.items():
        for option, coord in options.items():
            if not isinstance(coord, list) or len(coord) != 2:
                raise ValueError(f"Noto'g'ri koordinata formati: {coord}")
            try:
                # Float koordinatalarni int formatga o'tkazish
                x, y = map(int, coord)
            except ValueError:
                raise ValueError(f"Noto'g'ri koordinata qiymati: {coord}")
            
            radius = 5
            roi = image[y - radius:y + radius, x - radius:x + radius]
            mean_brightness = np.mean(roi)
            if mean_brightness < threshold:
                marked_answers[question] = option
                break
    return marked_answers


def extract_id(image_path, id_coordinates, threshold=200):
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    id_result = {}
    for digit, positions in id_coordinates.items():
        for number, coord in positions.items():
            if not isinstance(coord, list) or len(coord) != 2:
                raise ValueError(f"Noto'g'ri koordinata formati: {coord}")
            x, y = map(int, coord)
            radius = 5
            roi = image[y - radius:y + radius, x - radius:x + radius]
            mean_brightness = np.mean(roi)
            if mean_brightness < threshold:
                if digit not in id_result:
                    id_result[digit] = number
                break
    return ''.join([id_result.get(f'n{i}', '?') for i in range(1, 5)])

def find_image_files(directory):
    image_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_files.append(os.path.join(root, file))
    return image_files

class ProcessZipFileView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ZipFileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        zip_file = serializer.validated_data['file']
        zip_path = os.path.join(settings.MEDIA_ROOT, zip_file.name)
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        try:
            # ZIP faylni saqlash
            with open(zip_path, 'wb') as f:
                for chunk in zip_file.chunks():
                    f.write(chunk)

            # Fayllarni ochish
            extracted_dir = os.path.join(settings.MEDIA_ROOT, 'extracted')
            os.makedirs(extracted_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extracted_dir)

            # Rasmlarni topish
            image_files = find_image_files(extracted_dir)
            if not image_files:
                raise ValueError("Hech qanday rasm fayli topilmadi!")

            # Ma'lumotlar bazasidan barcha savollarni olish
            questions_db = Zip.objects.all()
            questions_dict = {q.text: q for q in questions_db}

            # Rasmlar bilan ishlash
            total_score = 0
            results = []
            with transaction.atomic():
                for image_path in image_files:
                    marked_answers = check_marked_circle(image_path, load_coordinates_from_json(COORDINATES_PATH))
                    student_id = extract_id(image_path, load_coordinates_from_json(ID_PATH))

                    # Har bir belgini to'g'ri javob bilan taqqoslash
                    for question_text, student_answer in marked_answers.items():
                        if question_text in questions_dict:
                            question = questions_dict[question_text]

                            # Kategoriyaga ko'ra ballarni hisoblash
                            score = 0
                            if question.category == "Majburiy Fan 1":
                                score = 1.1
                            elif question.category == "Majburiy Fan 2":
                                score = 1.1
                            elif question.category == "Majburiy Fan 3":
                                score = 1.1
                            elif question.category == "Fan 1":
                                score = 2.1
                            elif question.category == "Fan 2":
                                score = 3.1

                            # Javobni to'g'riligi bo'yicha hisoblash
                            is_correct = question.true_answer == student_answer
                            if is_correct:
                                total_score += score

                            # Natijani saqlash
                            result = ProcessedTestResult.objects.create(
                                student_id=student_id,
                                question_id=question.id,
                                student_answer=student_answer,
                                is_correct=is_correct,
                                score=score if is_correct else 0
                            )
                            results.append(result)

            # Umumiy natijalarni saqlash
            ProcessedTest.objects.create(
                student_id=student_id,
                total_score=total_score,
                image_url=upload_to_s3(image_path, f"images/answers/{os.path.basename(image_path)}")
            )

            return Response({"message": "Fayllar muvaffaqiyatli qayta ishladi.", "total_score": total_score}, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Xatolik yuz berdi: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        finally:
            # Vaqtinchalik fayllarni tozalash
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(extracted_dir):
                shutil.rmtree(extracted_dir)

