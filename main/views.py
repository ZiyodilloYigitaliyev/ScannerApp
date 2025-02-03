import os
import csv
import traceback
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .models import ProcessedTest, ProcessedTestResult
from rest_framework.permissions import AllowAny
import logging
import uuid
import json

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDINATES_PATH = os.path.join(BASE_DIR, 'app/coordinates/coordinates.csv')
ID_PATH = os.path.join(BASE_DIR, 'app/coordinates/coordinates.csv')
PHONE_NUMBER_PATH = os.path.join(BASE_DIR, 'app/coordinates/coordinates.csv')

def extract_from_coordinates(bubbles, coordinates_dict):
    """Koordinatalarni tekshirish va log qilishni kuchaytiramiz"""
    logger.info(
        "Koordinatalarni ajratish boshlandi. Bubbles soni: %d, Koordinatalar to'plami: %s", 
        len(bubbles), list(coordinates_dict.keys())
    )
    
    if not bubbles:
        logger.error("Bubbles bo'sh! Ajratib bo'lmaydi.")
        return None
        
    if not coordinates_dict:
        logger.error("Koordinatalar bo'sh! Ajratib bo'lmaydi.")
        return None

    logger.debug("Har bir koordinata to'plami uchun tekshirish:")
    for key, coord_list in coordinates_dict.items():
        logger.debug("%s uchun %d ta koordinata tekshirilmoqda...", key, len(coord_list))
        for idx, coord in enumerate(coord_list, 1):
            logger.debug("Tekshirilayotgan koordinata [%d/%d]: %s", idx, len(coord_list), coord)
            if coord in bubbles:
                logger.info("Topildi: %s - %s", key, coord)
                return {key: coord}

    logger.warning("Hech qanday moslik topilmadi!")
    return None

def load_coordinates_from_csv(csv_path):
    """CSV fayllarini yuklashda loglarni to'liqroq qilish"""
    logger.info("➤ CSV yuklash boshlandi: %s", csv_path)
    data = {}
    try:
        with open(csv_path, 'r') as file:
            reader = csv.reader(file)
            headers = next(reader)
            for row in reader:
                key = row[0]
                coordinates = [(int(row[i]), int(row[i+1])) for i in range(1, len(row), 2)]
                data[key] = coordinates
            logger.info("✓ CSV muvaffaqiyatli yuklandi. Elementlar soni: %d", len(data))
            logger.debug("Namuna ma'lumot: %s", str(data)[:100])
            return data
    except FileNotFoundError:
        logger.critical("⚠️ File topilmadi: %s", csv_path, exc_info=True)
        raise
    except Exception as e:
        logger.critical("⚠️ Noma'lum xato: %s", str(e), exc_info=True)
        raise

class ProcessImageView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        transaction_id = str(uuid.uuid4())[:8]  # Unique transaction ID
        logger.info("⎈⎈⎈ Yangi so'rov qabul qilindi ⎈⎈⎈ | Transaction ID: %s", transaction_id)
        logger.debug("So'rov tafsilotlari:\n%s", json.dumps(request.data, indent=2))

        try:
            # Validatsiya bosqichi
            if not request.data:
                logger.error("✖︎ Bo'sh JSON qabul qilindi!", extra={'transaction_id': transaction_id})
                return Response(
                    {"error": "Bo'sh JSON Yuborildi"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            file_url = request.data.get('file_url')
            bubbles = request.data.get('bubbles')
            logger.info("⌛ Validatsiya boshlandi. File URL: %s", file_url)

            if not all([file_url, bubbles]):
                logger.error("✖︎ Noto'g'ri ma'lumotlar: %s", 
                            "file_url yo'q" if not file_url else "bubbles yo'q",
                            extra={'transaction_id': transaction_id})
                return Response(
                    {"error": "Invalid data", "details": "missing file_url or bubbles"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Telefon raqamini qidirish
            logger.info("⎇ Telefon raqamini qidirish...")
            phone_coords = load_coordinates_from_csv(PHONE_NUMBER_PATH)
            phone_number = extract_from_coordinates(bubbles, phone_coords)
            logger.info("☎ Telefon raqam natijasi: %s", phone_number or "Topilmadi")

            # Student ID qidirish
            logger.info("⎇ Student ID qidirish...")
            student_coords = load_coordinates_from_csv(ID_PATH)
            student_id = extract_from_coordinates(bubbles, student_coords)
            logger.info("🆔 Student ID natijasi: %s", student_id or "Topilmadi")

            if not student_id:
                logger.error("✖︎ Student ID topilmadi!", extra={'transaction_id': transaction_id})
                return Response(
                    {"error": "Student ID aniqlanmadi"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Javoblarni qidirish
            logger.info("⎇ Test javoblarini qidirish...")
            question_coords = load_coordinates_from_csv(COORDINATES_PATH)
            marked_answers = extract_from_coordinates(bubbles, question_coords)
            logger.info("📝 Javoblar natijasi: %s", 
                       json.dumps(marked_answers, indent=2) if marked_answers else "Javoblar topilmadi")

            # Ma'lumotlar bazasiga yozish
            logger.info("💾 Ma'lumotlar bazasiga yozish boshlandi...")
            with transaction.atomic():
                processed_test = ProcessedTest.objects.create(
                    file_url=file_url,
                    student_id=student_id,
                    phone_number=phone_number
                )
                logger.info("✓ ProcessedTest yaratildi | ID: %s", processed_test.id)

                if marked_answers:
                    for q, a in marked_answers.items():
                        ProcessedTestResult.objects.create(
                            test=processed_test,
                            question=q,
                            answer=a
                        )
                        logger.debug("✓ Javob saqlandi: Savol-%s ➔ %s", q, a)
                else:
                    logger.warning("⚠️ Saqlanadigan javoblar yo'q!")

            logger.info("✅ So'rov muvaffaqiyatli yakunlandi!")
            return Response({
                "message": "Ma'lumotlar saqlandi",
                "transaction_id": transaction_id,
                "details": {
                    "student_id": student_id,
                    "phone_number": phone_number,
                    "answers_count": len(marked_answers) if marked_answers else 0
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.critical("‼️‼️ Kritik xato ‼️‼️ | Transaction ID: %s | Xato: %s", 
                          transaction_id, str(e), exc_info=True)
            logger.debug("Xato tafsilotlari: %s", traceback.format_exc())
            return Response(
                {"error": "Server xatosi", "transaction_id": transaction_id},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )