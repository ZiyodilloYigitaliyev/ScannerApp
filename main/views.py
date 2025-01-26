import json
import os
from django.http import JsonResponse
from rest_framework.views import APIView
from django.conf import settings
from .models import ProcessedData  # Modelga mos nomni ishlating
from rest_framework.permissions import AllowAny

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

            student_id = extract_from_coordinates(bubbles, id_coordinates)
            phone_number = extract_from_coordinates(bubbles, phone_number_coordinates)

            # Savollarning javoblarini tekshirish
            question_coordinates = load_coordinates_from_json(COORDINATES_PATH)
            marked_answers = extract_from_coordinates(bubbles, question_coordinates)

            # Natijani saqlash
            with transaction.atomic():
                processed_test = ProcessedTest.objects.create(
                    file=s3_url,
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
            return Response({
                "message": "Ma'lumotlar muvaffaqiyatli saqlandi.",
                "file_url": s3_url,
                "student_id": student_id,
                "phone_number": phone_number,
                "answers": marked_answers
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


def extract_from_coordinates(bubbles, coordinates):
    """
    JSON'dagi bubbles ma'lumotlari va koordinatalar bo'yicha mos ma'lumotlarni ajratib olish.
    :param bubbles: JSON'dan kelgan bubbles
    :param coordinates: Koordinatalar (JSON'dan yuklangan)
    """
    extracted_data = {}

    for key, coord_list in coordinates.items():
        for index, coord in enumerate(coord_list):
            if coord in bubbles:  # Agar koordinata bubbles ichida bo'lsa
                extracted_data[key] = index + 1  # Variant raqamini saqlash

    return extracted_data
