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

def extract_from_coordinates(bubbles, coordinates):
    if not bubbles or not coordinates:
        return None
    for coord_list in coordinates.values():
        for coord in coord_list:
            if coord in bubbles:
                return coord  # To'g'ri raqamni qaytarish
    return None

class ProcessImageView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            log_entries = []  # Log yozuvlarini saqlash uchun ro'yxat
            log_entries.append("Request received")

            # Ma'lumotlarni validatsiya qilish
            serializer = ProcessedTestSerializer(data=request.data)
            if not request.data:
                log_entries.append("Empty JSON received")
                return Response(
                    {"error": "Bo'sh JSON Yuborildi"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not serializer.is_valid():
                log_entries.append(f"Invalid data: {serializer.errors}")
                return Response(
                    {"error": "Invalid data", "details": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            log_entries.append("Data validated")

            # JSON'dagi s3url va bubbles ma'lumotlarini olish
            s3_url = serializer.validated_data.get('file_url')
            bubbles = serializer.validated_data.get('bubbles')
            log_entries.append(f"s3_url: {s3_url}, bubbles: {bubbles}")

            # Telefon raqami va IDni aniqlash
            phone_number_coordinates = load_coordinates_from_json(PHONE_NUMBER_PATH)
            phone_number = extract_from_coordinates(bubbles, phone_number_coordinates)

            student_id_coordinates = load_coordinates_from_json(ID_PATH)
            student_id = extract_from_coordinates(bubbles, student_id_coordinates)

            if student_id is None:
                log_entries.append("Student ID not found")
                return Response(
                    {"error": "Student ID aniqlanmadi"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            log_entries.append(f"Student ID: {student_id}, Phone number: {phone_number}")

            # Savollarning javoblarini tekshirish
            question_coordinates = load_coordinates_from_json(COORDINATES_PATH)
            marked_answers = extract_from_coordinates(bubbles, question_coordinates)
            log_entries.append(f"Marked answers: {marked_answers}")

            # Natijani saqlash
            with transaction.atomic():
                processed_test = ProcessedTest.objects.create(
                    file_url=s3_url,
                    student_id=student_id,
                    phone_number=phone_number
                )

                # Natijalarni saqlash
                for question, answer in marked_answers.items():
                    ProcessedTestResult.objects.create(
                        test=processed_test,
                        question=question,
                        answer=answer
                    )

            # Javob qaytarish
            response = {
                "message": "Ma'lumotlar muvaffaqiyatli saqlandi.",
                "file_url": s3_url,
                "student_id": student_id,
                "phone_number": phone_number,
                "answers": marked_answers
            }
            log_entries.append("Data saved successfully")
            print("\n".join(log_entries))  # Log yozuvlarini chop etish

            return Response(response, status=status.HTTP_201_CREATED)

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
