import requests
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from django.http import FileResponse
from io import BytesIO
from bs4 import BeautifulSoup
import datetime
from rest_framework.views import APIView
from urllib.parse import urlparse
import os
from django.conf import settings
import re


class GeneratePDFView(APIView):
    def get(self, request, *args, **kwargs):
        # API URL manzilini olish
        api_url = request.GET.get("api_url")

        if not api_url:
            return FileResponse(
                BytesIO(b"Error: 'api_url' parameter is required."),
                content_type="text/plain",
            )

        # APIdan ma'lumotlarni olish
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            api_data = response.json()
        except requests.exceptions.RequestException as e:
            return FileResponse(
                BytesIO(f"Error fetching API data: {str(e)}".encode("utf-8")),
                content_type="text/plain",
            )

        # PDFni yaratish
        pdf_buffer = generate_pdf_from_cleaned_data(api_data.get("data", {}))

        # PDFni yuklash uchun response qaytarish
        return FileResponse(
            pdf_buffer, as_attachment=True, filename="Questions_Report.pdf"
        )


def clean_options(options_text):

    pattern = r"(A\)|B\)|C\)|D\))\s*(https?:\/\/[^\s]+)"
    matches = re.findall(pattern, options_text)

    # To'g'ri formatni yaratish
    cleaned_options = ""
    for match in matches:
        cleaned_options += f"{match[0]} {match[1].strip()}    "  # A) https://... ko'rinishida yig'ish

    # Agar noto'g'ri format bo'lsa
    if not cleaned_options:
        return "Variantlar noto‘g‘ri formatda."
    return cleaned_options.strip()



def clean_html_tags(html_text):
    """HTML matnni tozalash uchun funksiya."""
    soup = BeautifulSoup(html_text, "html.parser")
    return soup


# Vaqtincha rasm saqlash joyi
TEMP_DIR = os.path.join(settings.BASE_DIR, 'temp_images')  # Django loyihasidagi asosiy papka ichida 'temp_images' papkasini yaratish

# TEMP_DIR papkasini yaratish agar u mavjud bo'lmasa
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


def generate_pdf_from_cleaned_data(data):
    """Tozalangan ma'lumotlardan PDF yaratish."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle("Questions Report")
    pdf.setFont("Times-Roman", 16)

    # PDF Header
    pdf.drawString(50, 750, "Questions Report")
    pdf.setFont("Times-Roman", 12)
    pdf.drawString(50, 730, f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    y_position = 700  # PDFda boshlang'ich yozish joyi

    for category, questions in data.items():
        # Kategoriya nomini qo'shish
        pdf.setFont("Times-Roman", 14)
        pdf.drawString(50, y_position, f"Category: {category}")
        y_position -= 20

        for question in questions:
            # Savol matni
            question_text = clean_html_tags(question.get("text", ""))
            options_text = question.get("options", "")
            true_answer = question.get("true_answer", "")

            pdf.setFont("Times-Roman", 12)
            pdf.drawString(50, y_position, question_text.get_text(strip=True))
            y_position -= 20

            # Variantlarni tozalash
            cleaned_options = clean_options(options_text)
            pdf.setFont("Times-Roman", 10)
            pdf.drawString(70, y_position, f"Options: {cleaned_options}")
            y_position -= 20

            # To'g'ri javob
            pdf.drawString(70, y_position, f"Correct Answer: {true_answer}")
            y_position -= 40  # Keyingi savol uchun joy qoldirish

            # Rasmni joylashtirish (Agar rasm bor bo'lsa)
            images = question_text.find_all("img")
            for img_tag in images:
                img_url = img_tag.get("src", "")
                if img_url:
                    # Rasmni yuklab olish
                    image_response = requests.get(img_url, stream=True)
                    if image_response.status_code == 200:
                        image_extension = os.path.splitext(urlparse(img_url).path)[1]
                        image_filename = f"temp_image{image_extension}"
                        image_path = os.path.join(TEMP_DIR, image_filename)

                        with open(image_path, 'wb') as img_file:
                            img_file.write(image_response.content)

                        # Rasmni PDFga joylashtirish
                        pdf.drawImage(image_path, 50, y_position, width=1.0*inch, height=2.0*inch)
                        y_position -= 50

            # Sahifa tugashi bo'yicha yangi sahifa qo'shish
            if y_position < 50:
                pdf.showPage()
                y_position = 750

    # PDFni saqlash
    pdf.save()
    buffer.seek(0)
    return buffer
