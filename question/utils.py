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

def render_formula_to_image(formula):
    """Matematik formulani rasmga aylantiradi."""
    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()  # Tayyor shriftlardan foydalaniladi
    draw.text((10, 10), formula, fill="black", font=font)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

def extract_questions_with_images_and_save(docx_file, category, subject):
    """
    Word fayldan savollar, rasmlar va matematik formulalarni o'qib, ma'lumotlar bazasiga saqlaydi.
    """
    document = Document(docx_file)
    questions = []
    current_question = None

    for i, paragraph in enumerate(document.paragraphs):
        text = paragraph.text.strip()

        # Yangi savolni boshlash
        if text and text[0].isdigit() and '.' in text:
            if current_question:
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

            # Yangi savol uchun boshlang'ich ma'lumotlar
            current_question = {
                "text": text,
                "options": "",
                "true_answer": None,
                "images": []  # Rasmlar ro'yxati
            }

        # Variantlarni qo'shish
        elif text.startswith(("A)", "B)", "C)", "D)")) and current_question:
            current_question["options"] += text + '\n'

        # Rasmlarni o'qish yoki matematik formulani aniqlash
        for run in paragraph.runs:
            if run.element.xpath(".//w:drawing"):
                image_parts = run.element.xpath(".//w:blip/@r:embed")

                if image_parts:
                    image_part = image_parts[0]
                    if image_part is not None:
                        image = document.part.related_parts.get(image_part)
                        if image is not None:
                            current_question["images"].append({
                                "filename": f"image_{uuid.uuid4().hex}.png",
                                "content": image.blob
                            })

            # Matematik formulalarni aniqlash va rasmga aylantirish
            elif "\\(" in text and "\\)" in text:
                formula_start = text.find("\\(") + 2
                formula_end = text.find("\\)")
                formula = text[formula_start:formula_end]

                # Formulani rasmga aylantirish
                formula_image = render_formula_to_image(formula)
                file_name = f"formula_{uuid.uuid4().hex}.png"

                # S3 ga saqlash
                s3_url = upload_image_to_s3(formula_image, file_name)

                # Formulaning o'rniga S3 URLni qo'shish
                text = text.replace(f"\\({formula}\\)", s3_url)

        # Paragraf matnini yangilash
        paragraph.text = text

    # Oxirgi savolni saqlash
    if current_question:
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
