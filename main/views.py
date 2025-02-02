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

def extract_from_coordinates(bubbles, student_id_coordinates):
    logger.info("extract_from_coordinates called with bubbles: %s and coordinates: %s", bubbles, coordinates)
    if not bubbles or not student_id_coordinates:
        logger.warning("bubbles or coordinates are empty")
        return None
    for coord_list in coordinates.values():
        for coord in coord_list:
            if coord in bubbles:
                logger.info("Match found: %s", coord)
                return coord  # To'g'ri raqamni qaytarish
    logger.info("No match found")
    return None

class ProcessImageView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            logger.info("Request received")

            # Ma'lumotlarni validatsiya qilish
            if not request.data:
                logger.warning("Empty JSON received")
                return Response(
                    {"error": "Bo'sh JSON Yuborildi"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            file_url = request.data.get('file_url')
            bubbles = request.data.get('bubbles')

            if not file_url or not bubbles:
                logger.warning("Invalid data: missing file_url or bubbles")
                return Response(
                    {"error": "Invalid data", "details": "missing file_url or bubbles"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"Data validated: file_url={file_url}, bubbles={bubbles}")

            # Telefon raqami va IDni aniqlash
            phone_number_coordinates = load_coordinates_from_json(PHONE_NUMBER_PATH)
            phone_number = extract_from_coordinates(bubbles, phone_number_coordinates)

            student_id_coordinates = load_coordinates_from_json(ID_PATH)
            student_id = extract_from_coordinates(bubbles, student_id_coordinates)

            if student_id is None:
                logger.warning("Student ID not found")
                return Response(
                    {"error": "Student ID aniqlanmadi"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"Student ID: {student_id}, Phone number: {phone_number}")

            # Savollarning javoblarini tekshirish
            question_coordinates = load_coordinates_from_json(COORDINATES_PATH)
            marked_answers = extract_from_coordinates(bubbles, question_coordinates)
            logger.info(f"Marked answers: {marked_answers}")

            # Natijani saqlash
            with transaction.atomic():
                processed_test = ProcessedTest.objects.create(
                    file_url=file_url,
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
                "file_url": file_url,
                "student_id": student_id,
                "phone_number": phone_number,
                "answers": marked_answers
            }
            logger.info("Data saved successfully")

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
