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

# Fayllar yo‘li
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
            x, y = map(int, coord)
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
    """ Katalog ichidan rasm fayllarini topish """
    image_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):  # Faqat rasm fayllari
                image_files.append(os.path.join(root, file))
    return image_files

class ProcessZipFileView(APIView):
    def get(self, request, *args, **kwargs):
        processed_tests = ProcessedTest.objects.all()
        serializer = ProcessedTestSerializer(processed_tests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = ZipFileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        zip_file = serializer.validated_data['file']
        zip_path = os.path.join(settings.MEDIA_ROOT, zip_file.name)
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        # Zipni saqlash
        with open(zip_path, 'wb') as f:
            for chunk in zip_file.chunks():
                f.write(chunk)

        # Zipni ochish
        extracted_dir = os.path.join(settings.MEDIA_ROOT, 'extracted')
        os.makedirs(extracted_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extracted_dir)

            # JSON fayllarni yuklash
            coordinates = load_coordinates_from_json(COORDINATES_PATH)['coordinates']
            id_coordinates = load_coordinates_from_json(ID_PATH)['id']

            # Rasmlarni topish
            image_files = find_image_files(extracted_dir)
            if not image_files:
                raise ValueError("Hech qanday rasm fayli topilmadi!")

            results = []
            with transaction.atomic():
                for image_path in image_files:
                    marked_answers = check_marked_circle(image_path, coordinates)
                    student_id = extract_id(image_path, id_coordinates)

                    # `QuestionList` modelida list_id bilan tekshirish
                    try:
                        question_list = QuestionList.objects.get(list_id=student_id)
                    except QuestionList.DoesNotExist:
                        return Response({'error': f"Student ID {student_id} bazada topilmadi."},
                                        status=status.HTTP_400_BAD_REQUEST)

                    student_test = ProcessedTest.objects.create(student_id=student_id)
                    # Savollarni tekshirish
                    for question_id, student_answer in marked_answers.items():
                        try:
                            true_answer = Question.objects.get(
                                list=question_list,
                                question_id=question_id
                            )
                            is_correct = true_answer.true_answer == student_answer
                        except Question.DoesNotExist:
                            is_correct = False

                        # Natijalarni saqlash
                        result = ProcessedTestResult.objects.create(
                            student=student_test,
                            question_id=question_id,
                            student_answer=student_answer,
                            is_correct=is_correct
                        )

                    # Rasmni S3ga yuklash va URLni saqlash
                    s3_key = f"images/answers/{os.path.basename(image_path)}"
                    s3_url = upload_to_s3(image_path, s3_key)
                    # S3 URLni tekshirish
                    if not s3_url:
                        raise ValueError(f"S3 URL olishda xatolik: {image_path}")
                    # `ProcessedTest` modeliga rasm URL'ni saqlash
                    student_test.image_url = s3_url
                    student_test.save()
                data = {"message": "Success"}
            return Response(data, status=status.HTTP_201_CREATED)



        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        finally:
            # Zip faylni o'chirish
            if os.path.exists(zip_path):
                os.remove(zip_path)

            # Extracted katalogni o'chirish
            try:
                shutil.rmtree(extracted_dir)
            except Exception as e:
                print(f"Katalogni o'chirishda xatolik: {extracted_dir} -> {e}")
