from docx import Document
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import io
import boto3
import uuid
from .models import QuestionImage, Zip
import os
from concurrent.futures import ThreadPoolExecutor
from tempfile import NamedTemporaryFile
from django.conf import settings
import xml.etree.cElementTree as ET 

def upload_image_to_s3(self, image_name, image_data):
            s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME

            file_name, file_extension = os.path.splitext(image_name)
            unique_name = file_name
            s3_key = f"images/{unique_name}{file_extension}"

            while self.check_file_exists_in_s3(s3_client, bucket_name, s3_key):
                unique_name = f"{uuid.uuid4().hex}{file_extension}"
                s3_key = f'images/{unique_name}'

            with NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(image_data)
                temp_file.close()
                s3_client.upload_file(temp_file.name, bucket_name, s3_key,  ExtraArgs={"ACL": "public-read"})
                os.unlink(temp_file.name)

            return f'https://{bucket_name}.s3.amazonaws.com/{s3_key}'

def upload_images_concurrently(self, images):
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self.upload_image_to_s3, img_name, img_data): img_name for img_name, img_data in images.items()}
            return {future.result(): images[future] for future in futures}
def check_file_exists_in_s3(self, s3_client, bucket_name, s3_key):
        try:
            s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            return True
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                raise

def parse_svg(svg_content):
    """SVG faylni o'qib, uning tarkibiy qismlarini qaytaradi."""
    try:
        root = ET.fromstring(svg_content)
        elements = []
        for elem in root.iter():
            elements.append(elem.tag)
        return elements
    except ET.ParseError as e:
        return {"error": f"SVG faylni o'qishda xato: {e}"}

# Matematik formulani PNG rasmga aylantirish
def render_formula_to_image(formula):
    """Matematik formulani rasmga aylantiradi."""
    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((10, 10), formula, fill="black", font=font)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

def extract_questions_from_svg(svg_file, category, subject):
    """
    SVG fayldan savollar va elementlarni o'qib, ma'lumotlar bazasiga saqlaydi.
    """
    svg_content = svg_file.read().decode("utf-8")
    svg_elements = parse_svg(svg_content)

    # Savollarni tahlil qilish va saqlash uchun boshlang'ich sozlamalar
    questions = []
    current_question = {
        "text": "",
        "options": "",
        "true_answer": None,
        "images": []
    }

    for elem in svg_elements:
        # Bu yerda SVG elementlari asosida savollarni tahlil qilishingiz mumkin
        if "question" in elem:
            if current_question["text"]:
                question_obj = Zip.objects.create(
                    text=current_question["text"],
                    options=current_question["options"],
                    true_answer=current_question["true_answer"],
                    category=category,
                    subject=subject
                )

                # Rasmni saqlash
                for image_data in current_question["images"]:
                    image_file = ContentFile(image_data["content"], name=image_data["filename"])
                    QuestionImage.objects.create(question=question_obj, image=image_file)

            current_question = {
                "text": elem,  # Savol matni
                "options": "",
                "true_answer": None,
                "images": []
            }
        elif "option" in elem:
            current_question["options"] += elem + "\n"
        elif "image" in elem:
            # SVG ichidagi rasmlarni qayta ishlash
            current_question["images"].append({
                "filename": f"image_{uuid.uuid4().hex}.svg",
                "content": svg_content
            })

    # Oxirgi savolni saqlash
    if current_question["text"]:
        question_obj = Zip.objects.create(
            text=current_question["text"],
            options=current_question["options"],
            true_answer=current_question["true_answer"],
            category=category,
            subject=subject
        )
        for image_data in current_question["images"]:
            image_file = ContentFile(image_data["content"], name=image_data["filename"])
            QuestionImage.objects.create(question=question_obj, image=image_file)

    return len(questions)
