import os
import json
import boto3
from rest_framework.fields import FileField, ListField, IntegerField
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
import uuid

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDINATES_PATH = os.path.join(BASE_DIR, 'app/coordinates/coordinates.json')
ID_PATH = os.path.join(BASE_DIR, 'app/coordinates/id.json')
PHONE_NUMBER_PATH = os.path.join(BASE_DIR, 'app/coordinates/number_id.json')  # Telefon raqami koordinatalari

class ProcessImageView(APIView):
    permission_classes = [AllowAny]
    file = FileField(required=True)  # Fayl maydoni
    bubbles = ListField(
        child=ListField(
            child=IntegerField(),  # Har bir koordinata integer bo'lishi kerak
            min_length=2,  # Har bir koordinata [x, y] shaklida bo'lishi kerak
            max_length=2
        ),
        required=True
    )
    def post(self, request, *args, **kwargs):
        try:
            # Fayl va bubbles ma'lumotlarini tekshirish
            serializer = ProcessedTestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({"error": "Invalid data", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            file = serializer.validated_data.get('file')
            bubbles = serializer.validated_data.get('bubbles')

            # Faylni serverga vaqtinchalik saqlash
            image_path = os.path.join(settings.MEDIA_ROOT, file.name)
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

            with open(image_path, 'wb') as f:
                for chunk in file.chunks():
                    f.write(chunk)

            # Telefon raqami va IDni aniqlash
            id_coordinates = load_coordinates_from_json(ID_PATH)
            phone_number_coordinates = load_coordinates_from_json(PHONE_NUMBER_PATH)
            student_id = extract_id(image_path, id_coordinates)
            phone_number = extract_phone_number(image_path, phone_number_coordinates)

            # Savollarning javoblarini tekshirish
            coordinates = load_coordinates_from_json(COORDINATES_PATH)
            marked_answers = check_marked_circle(image_path, coordinates)

            # Savollarni DBdan olish
            questions_db = Zip.objects.all()
            questions_dict = {q.text: q for q in questions_db}

            total_score = 0

            # Transaction doirasida saqlash
            with transaction.atomic():
                for question_text, student_answer in marked_answers.items():
                    if question_text in questions_dict:
                        question = questions_dict[question_text]

                        # Savolga to'g'ri javob berilganligini tekshirish
                        score = 0
                        if question.category == "Majburiy Fan 1":
                            score = 1.1
                        elif question.category == "Fan 1":
                            score = 2.1
                        elif question.category == "Fan 2":
                            score = 3.1

                        is_correct = question.true_answer == student_answer
                        if is_correct:
                            total_score += score

                        ProcessedTestResult.objects.create(
                            student_id=student_id,
                            question_id=question.id,
                            student_answer=student_answer,
                            is_correct=is_correct,
                            score=score if is_correct else 0
                        )

            # Faylni S3 ga yuklash
            unique_s3_key = ensure_unique_s3_key(f"images/answers/{file.name}")
            image_url = upload_to_s3(image_path, unique_s3_key)

            # Natijani saqlash
            processed_test = ProcessedTest.objects.create(
                file=image_url,
                bubbles=marked_answers,
                total_score=total_score,
                phone_number=phone_number
            )

            # Faylni o'chirish
            if os.path.exists(image_path):
                os.remove(image_path)

            # Javob qaytarish
            return Response({
                "message": "Fayl muvaffaqiyatli yuklandi va qayta ishladi.",
                "file_url": image_url,
                "student_id": student_id,
                "phone_number": phone_number,
                "total_score": total_score
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Xatolik yuz berdi: {str(e)}")
            return Response({"error": f"Serverda xatolik yuz berdi: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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


def ensure_unique_s3_key(s3_key):
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION_NAME
    )
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    try:
        s3.head_object(Bucket=bucket_name, Key=s3_key)
        base, ext = os.path.splitext(s3_key)
        unique_key = f"{base}_{uuid.uuid4().hex[:8]}{ext}"
        return ensure_unique_s3_key(unique_key)
    except s3.exceptions.ClientError:
        return s3_key


def load_coordinates_from_json(json_path):
    with open(json_path, 'r') as file:
        return json.load(file)


def check_marked_circle(image_path, coordinates, threshold=200):
    marked_answers = {}

    # Koordinatalarni tekshirish
    for question, options in coordinates.items():
        for option, coord in options.items():
            # Har bir koordinata [x, y] shaklida bo'lishi kerak
            if isinstance(coord, (list, tuple)) and len(coord) == 2:
                x, y = map(int, coord)
                marked_answers[question] = option
            else:
                logger.error(f"Invalid coordinate format for {question}-{option}: {coord}")

    return marked_answers




def extract_id(image_path, id_coordinates, threshold=200):
    id_result = {}

    for digit, positions in id_coordinates.items():
        for number, coord in positions.items():
            if isinstance(coord, (list, tuple)) and len(coord) == 2:
                x, y = map(int, coord)
                id_result[digit] = number
            else:
                logger.error(f"Invalid coordinate format for {digit}-{number}: {coord}")

    return ''.join([id_result.get(f'n{i}', '?') for i in range(1, 5)])



def extract_phone_number(image_path, phone_number_coordinates, threshold=200):
    phone_number = {}

    # phone_number_coordinates obyektidagi har bir raqam uchun koordinatalarni tekshirish
    for digit, positions in phone_number_coordinates.items():
        for number, coord in positions.items():
            # Koordinatalarni x, y ga o'zgartirish
            x, y = map(int, coord)
            phone_number[digit] = number

            # Natijada telefon raqami qaytariladi
        return ''.join([phone_number.get(f'n{i}', '?') for i in range(1, 5)])
