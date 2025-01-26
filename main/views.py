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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COORDINATES_PATH = os.path.join(BASE_DIR, 'app/coordinates/coordinates.json')
ID_PATH = os.path.join(BASE_DIR, 'app/coordinates/id.json')


def load_coordinates_from_json(json_path):
    """JSON fayldan koordinatalarni yuklaydi."""
    with open(json_path, 'r') as file:
        return json.load(file)

def check_marked_circle(image_path, coordinates, threshold=200):
    """
    Suratdagi belgilangan doirani aniqlaydi.
    
    :param image_path: Suratingiz fayl yo'li.
    :param coordinates: JSON orqali kelgan koordinatalar.
    :param threshold: Yorqinlik chegarasi.
    :return: Belgilangan javoblar lug'ati.
    """
    image = Image.open(image_path).convert("L")  # Suratni grayscale'ga o'tkazadi
    image_array = np.array(image)  # Suratingizni numpy massivga aylantiradi
    marked_answers = {}

    for question, options in coordinates.items():
        for option, coord in options.items():
            if not isinstance(coord, list) or len(coord) != 2:
                raise ValueError(f"Noto'g'ri koordinata formati: {coord}")
            x, y = map(int, coord)
            radius = 5
            roi = image_array[y - radius:y + radius, x - radius:x + radius]  # Region of Interest (ROI)
            mean_brightness = np.mean(roi)  # ROI ning yorqinlik o'rtachasi
            if mean_brightness < threshold:
                marked_answers[question] = option
                break
    return marked_answers

def extract_id(image_path, id_coordinates, threshold=200):
    """
    Suratdagi ID raqamlarini aniqlaydi.
    
    :param image_path: Suratingiz fayl yo'li.
    :param id_coordinates: JSON orqali kelgan ID koordinatalari.
    :param threshold: Yorqinlik chegarasi.
    :return: Topilgan ID raqami.
    """
    image = Image.open(image_path).convert("L")
    image_array = np.array(image)
    id_result = {}
    
    for digit, positions in id_coordinates.items():
        for number, coord in positions.items():
            if not isinstance(coord, list) or len(coord) != 2:
                raise ValueError(f"Noto'g'ri koordinata formati: {coord}")
            x, y = map(int, coord)
            radius = 5
            roi = image_array[y - radius:y + radius, x - radius:x + radius]
            mean_brightness = np.mean(roi)
            if mean_brightness < threshold:
                if digit not in id_result:
                    id_result[digit] = number
                break
    
    # ID raqamni ketma-ketlikda yig'adi
    return ''.join([id_result.get(f'n{i}', '?') for i in range(1, 5)])

def find_image_files(directory):
    """
    Berilgan papkadan barcha tasvirlarni topadi.
    
    :param directory: Papka yo'li.
    :return: Tasvirlar ro'yxati.
    """
    image_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_files.append(os.path.join(root, file))
    return image_files


class ProcessImageView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ProcessedTestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        image_file = serializer.validated_data['file']
        bubbles = serializer.validated_data['bubbles']

        image_path = os.path.join(settings.MEDIA_ROOT, image_file.name)
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        try:
            # Faylni saqlash
            with open(image_path, 'wb') as f:
                for chunk in image_file.chunks():
                    f.write(chunk)

            # JSONdan bubblesni o'qish
            if not bubbles:
                raise ValueError("Bubbles JSON ma'lumotlari mavjud emas!")

            # Ma'lumotlar bazasidan barcha savollarni olish
            questions_db = Zip.objects.all()
            questions_dict = {q.text: q for q in questions_db}

            # Bubbles ma'lumotlari bilan ishlash
            total_score = 0
            results = []
            with transaction.atomic():
                student_id = bubbles.get('student_id', None)
                marked_answers = bubbles.get('answers', {})

                # Har bir belgi uchun hisoblash
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

            # Rasmni S3 ga yuklash
            image_url = upload_to_s3(image_path, f"images/answers/{os.path.basename(image_path)}")

            # ProcessedTest modelini saqlash
            ProcessedTest.objects.create(
                student_id=student_id,
                bubbles=bubbles,
                total_score=total_score,
                image_url=image_url
            )

            return Response({"message": "Fayl muvaffaqiyatli qayta ishladi.", "total_score": total_score}, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Xatolik yuz berdi: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        finally:
            # Fayllarni tozalash
            if os.path.exists(image_path):
                os.remove(image_path)


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

