import os
import json
import boto3
import numpy as np
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.db import transaction
from .serializers import ProcessedTestSerializer
from .models import ProcessedTest, ProcessedTestResult
from rest_framework.permissions import AllowAny
import logging
from question.models import Zip
from PIL import Image
logger = logging.getLogger(__name__)
import uuid

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDINATES_PATH = os.path.join(BASE_DIR, 'app/coordinates/coordinates.json')
ID_PATH = os.path.join(BASE_DIR, 'app/coordinates/id.json')


class ProcessImageView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ProcessedTestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        image_files = serializer.validated_data['files']  # Bir nechta fayllarni olish
        if len(image_files) < 2:  # Minimal 2 ta faylni tekshirish
            return Response({"error": "Kamida 2 ta fayl yuklashingiz kerak!"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # JSON koordinatalarni yuklash
            coordinates = load_coordinates_from_json(COORDINATES_PATH)
            id_coordinates = load_coordinates_from_json(ID_PATH)

            results = []  # Natijalarni yig‘ish uchun
            total_score = 0

            for image_file in image_files:
                image_path = os.path.join(settings.MEDIA_ROOT, image_file.name)
                os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

                # Faylni vaqtinchalik saqlash
                with open(image_path, 'wb') as f:
                    for chunk in image_file.chunks():
                        f.write(chunk)

                # ID raqamni chiqarish
                student_id = extract_id(image_path, id_coordinates)

                # Belgilangan savollarni aniqlash
                marked_answers = check_marked_circle(image_path, coordinates)

                # Savollardan ballar hisoblash
                questions_db = Zip.objects.all()
                questions_dict = {q.text: q for q in questions_db}

                with transaction.atomic():
                    for question_text, student_answer in marked_answers.items():
                        if question_text in questions_dict:
                            question = questions_dict[question_text]

                            # Kategoriyaga ko‘ra ballarni hisoblash
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

                            # Javobni to‘g‘riligi bo‘yicha hisoblash
                            is_correct = question.true_answer == student_answer
                            if is_correct:
                                total_score += score

                            # Natijani saqlash
                            ProcessedTestResult.objects.create(
                                student_id=student_id,
                                question_id=question.id,
                                student_answer=student_answer,
                                is_correct=is_correct,
                                score=score if is_correct else 0
                            )

                # Faylni S3 bucketga yuklash
                unique_s3_key = ensure_unique_s3_key(f"images/answers/{image_file.name}")
                image_url = upload_to_s3(image_path, unique_s3_key)

                # ProcessedTest yozuvini yaratish
                processed_test = ProcessedTest.objects.create(
                    file=image_url,
                    bubbles=marked_answers,
                    total_score=total_score
                )
                results.append({
                    "file_url": image_url,
                    "student_id": student_id,
                    "total_score": total_score
                })

                # Vaqtinchalik faylni o'chirish
                if os.path.exists(image_path):
                    os.remove(image_path)

            return Response({
                "message": "Fayllar muvaffaqiyatli qayta ishladi.",
                "results": results
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Xatolik yuz berdi: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def upload_to_s3(file_path, s3_key):
    """Faylni S3 bucketga yuklash."""
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


def ensure_unique_s3_key(s3_key):
    """
    Fayl nomini tekshiradi. Agar nom mavjud bo'lsa, yangi nom yaratadi.
    """
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION_NAME
    )
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    try:
        s3.head_object(Bucket=bucket_name, Key=s3_key)
        # Agar fayl mavjud bo'lsa, yangi nom yaratish
        base, ext = os.path.splitext(s3_key)
        unique_key = f"{base}_{uuid.uuid4().hex[:8]}{ext}"
        return ensure_unique_s3_key(unique_key)
    except s3.exceptions.ClientError:
        return s3_key


def load_coordinates_from_json(json_path):
    with open(json_path, 'r') as file:
        return json.load(file)


def check_marked_circle(image_path, coordinates, threshold=200):
    image = Image.open(image_path).convert("L")
    image_array = np.array(image)
    marked_answers = {}

    for question, options in coordinates.items():
        for option, coord in options.items():
            x, y = map(int, coord)
            radius = 5
            roi = image_array[y - radius:y + radius, x - radius:x + radius]
            mean_brightness = np.mean(roi)
            if mean_brightness < threshold:
                marked_answers[question] = option
                break
    return marked_answers


def extract_id(image_path, id_coordinates, threshold=200):
    image = Image.open(image_path).convert("L")
    image_array = np.array(image)
    id_result = {}

    for digit, positions in id_coordinates.items():
        for number, coord in positions.items():
            x, y = map(int, coord)
            radius = 5
            roi = image_array[y - radius:y + radius, x - radius:x + radius]
            mean_brightness = np.mean(roi)
            if mean_brightness < threshold:
                if digit not in id_result:
                    id_result[digit] = number
                break

    return ''.join([id_result.get(f'n{i}', '?') for i in range(1, 5)])
