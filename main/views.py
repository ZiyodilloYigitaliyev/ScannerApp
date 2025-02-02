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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDINATES_PATH = os.path.join(BASE_DIR, 'app/coordinates/coordinates.json')
ID_PATH = os.path.join(BASE_DIR, 'app/coordinates/id.json')
PHONE_NUMBER_PATH = os.path.join(BASE_DIR, 'app/coordinates/number_id.json')

def extract_from_coordinates(bubbles, coordinates):
    logger.info("extract_from_coordinates called with bubbles: %s and coordinates: %s", bubbles, coordinates)
    if not bubbles or not coordinates:
        logger.warning("bubbles or coordinates are empty")
        return None
    for key, coord_list in coordinates.items():
        for coord in coord_list:
            if coord in bubbles:
                logger.info("Match found: %s for key: %s", coord, key)
                return key  
    logger.info("No match found")
    return None

def load_coordinates_from_json(json_path):
    """JSON faylidan koordinatalarni yuklash"""
    try:
        logger.info("Loading coordinates from JSON: %s", json_path)
        with open(json_path, 'r') as file:
            data = json.load(file)
        logger.info("Coordinates loaded successfully: %s", data)
        return data
    except Exception as e:
        logger.error("Error loading JSON file %s: %s", json_path, str(e))
        return {}

class ProcessImageView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            logger.info("Request received with data: %s", request.data)

            if not request.data:
                logger.warning("Empty JSON received")
                return Response({"error": "Bo'sh JSON Yuborildi"}, status=status.HTTP_400_BAD_REQUEST)

            file_url = request.data.get('file_url')
            bubbles = request.data.get('bubbles')

            if not file_url or not bubbles:
                logger.warning("Invalid data: missing file_url or bubbles")
                return Response({"error": "Invalid data", "details": "missing file_url or bubbles"}, status=status.HTTP_400_BAD_REQUEST)

            logger.info("Valid data received: file_url=%s, bubbles=%s", file_url, bubbles)

            phone_number_coordinates = load_coordinates_from_json(PHONE_NUMBER_PATH)
            phone_number = extract_from_coordinates(bubbles, phone_number_coordinates)
            logger.info("Extracted phone number: %s", phone_number)

            student_id_coordinates = load_coordinates_from_json(ID_PATH)
            student_id = extract_from_coordinates(bubbles, student_id_coordinates)
            logger.info("Extracted student ID: %s", student_id)

            if student_id is None:
                logger.warning("error: Student ID Coordinates Incorrect Format. Check the Coordinates")
                return Response({"error": "Student ID aniqlanmadi"}, status=status.HTTP_400_BAD_REQUEST)

            question_coordinates = load_coordinates_from_json(COORDINATES_PATH)
            marked_answers = extract_from_coordinates(bubbles, question_coordinates)
            logger.info("Extracted answers: %s", marked_answers)

            with transaction.atomic():
                logger.info("Saving ProcessedTest record")
                processed_test = ProcessedTest.objects.create(
                    file_url=file_url,
                    student_id=student_id,
                    phone_number=phone_number
                )

                for question, answer in (marked_answers or {}).items():
                    logger.info("Saving ProcessedTestResult: question=%s, answer=%s", question, answer)
                    ProcessedTestResult.objects.create(
                        test=processed_test,
                        question=question,
                        answer=answer
                    )

            response = {
                "message": "Ma'lumotlar muvaffaqiyatli saqlandi.",
                "file_url": file_url,
                "student_id": student_id,
                "phone_number": phone_number,
                "answers": marked_answers
            }
            logger.info("Response: %s", response)

            return Response(response, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error("Xatolik yuz berdi: %s", str(e), exc_info=True)
            return Response({"error": f"Serverda xatolik yuz berdi: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
