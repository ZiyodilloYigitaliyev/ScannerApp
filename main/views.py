import os
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .serializers import ProcessedTestSerializer
from .models import ProcessedTest, ProcessedTestResult
from rest_framework.permissions import AllowAny
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDINATES_PATH = os.path.join(BASE_DIR, 'app/coordinates/coordinates.json')
ID_PATH = os.path.join(BASE_DIR, 'app/coordinates/id.json')
PHONE_NUMBER_PATH = os.path.join(BASE_DIR, 'app/coordinates/number_id.json')  # Telefon raqami koordinatalari

class ProcessImageView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            # Ma'lumotlarni validatsiya qilish
            serializer = ProcessedTestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {"error": "Invalid data", "details": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # JSON'dagi s3url va bubbles ma'lumotlarini olish
            s3_url = serializer.validated_data.get('file_url')
            bubbles = serializer.validated_data.get('bubbles')  # JSONField orqali olinadigan ma'lumot

            # Telefon raqami va IDni aniqlash
            id_coordinates = load_coordinates_from_json(ID_PATH)
            phone_number_coordinates = load_coordinates_from_json(PHONE_NUMBER_PATH)
            student_id = extract_id(s3_url, id_coordinates)
            phone_number = extract_phone_number(s3_url, phone_number_coordinates)

            # Savollarning javoblarini tekshirish
            coordinates = load_coordinates_from_json(COORDINATES_PATH)

            # Natijani saqlash
            with transaction.atomic():
                processed_test = ProcessedTest.objects.create(
                    file=s3_url,
                    bubbles=bubbles,
                    phone_number=phone_number
                )

            # Javob qaytarish
            return Response({
                "message": "Ma'lumotlar muvaffaqiyatli saqlandi.",
                "file_url": s3_url,
                "student_id": student_id,
                "phone_number": phone_number
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Xatolik yuz berdi: {str(e)}")
            return Response(
                {"error": f"Serverda xatolik yuz berdi: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


def load_coordinates_from_json(json_path):
    """JSON faylidan koordinatalarni yuklash"""
    with open(json_path, 'r') as file:
        return json.load(file)


def extract_id(image_path, id_coordinates, threshold=200):
    """IDni rasmdan olish"""
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
    """Telefon raqamini rasmdan olish"""
    phone_number = {}

    # phone_number_coordinates obyektidagi har bir raqam uchun koordinatalarni tekshirish
    for digit, positions in phone_number_coordinates.items():
        for number, coord in positions.items():
            # Koordinatalarni x, y ga o'zgartirish
            if isinstance(coord, (list, tuple)) and len(coord) == 2:
                x, y = map(int, coord)
                phone_number[digit] = number

    return ''.join([phone_number.get(f'n{i}', '?') for i in range(1, 5)])


def check_marked_circle(image_path, coordinates, threshold=200):
    """Koordinatalarni tekshirish"""
    marked_answers = {}

    for question, options in coordinates.items():
        for option, coord in options.items():
            if isinstance(coord, (list, tuple)) and len(coord) == 2:
                x, y = map(int, coord)
                marked_answers[question] = option
            else:
                logger.error(f"Invalid coordinate format for {question}-{option}: {coord}")

    return marked_answers
