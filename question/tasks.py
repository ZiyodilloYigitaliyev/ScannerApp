from celery import shared_task
from bs4 import BeautifulSoup
import re
from .models import Zip
from .s3_utils import upload_image_to_s3 

@shared_task
def process_html_task(html_file, images, category, subject):
    soup = BeautifulSoup(html_file, 'html.parser')
    questions = []
    current_question = None

    # Rasmlarni S3 bucketga yuklash va URLni yangilash
    image_urls = {img_name: upload_image_to_s3(img_name, img_data) for img_name, img_data in images.items()}

    for img_tag in soup.find_all('img'):
        img_src = img_tag.get('src')
        if img_src in image_urls:
            img_tag['src'] = image_urls[img_src]
        else:
            img_tag.decompose()

    # "KEY" bo‘limini topish va true_answerlarni ajratib olish
    key_answers = []
    for p_tag in soup.find_all('p'):
        if "KEY" in p_tag.get_text(strip=True).upper():
            key_text = p_tag.get_text(strip=True)
            matches = re.findall(r'(\d+)-([A-D])', key_text)  # Masalan: 1-A, 2-B kabi formatni olish
            key_answers = [match[1] for match in sorted(matches, key=lambda x: int(x[0]))]
            break

    # Savollarni ajratib olish
    question_counter = 0
    for p_tag in soup.find_all('p'):
        text = p_tag.get_text(strip=True)
        if not text:
            continue

        # Yangi savolni boshlash
        if text[0].isdigit() and '.' in text:
            if current_question:
                questions.append(current_question)
            question_counter += 1
            current_question = {
                "text": str(p_tag),
                "options": "",
                "true_answer": None,
                "category": category,
                "subject": subject
            }

        # Variantlarni qo‘shish
        elif text.startswith(("A)", "B)", "C)", "D)")) and current_question:
            current_question["options"] += str(p_tag)

    if current_question:
        questions.append(current_question)

    # "KEY"dagi javoblarni savollarga biriktirish
    for i, question in enumerate(questions):
        if i < len(key_answers):
            question["true_answer"] = key_answers[i]

    # Ma'lumotlarni saqlash
    for question in questions:
        Zip.objects.create(
            text=question["text"],
            options=question["options"],
            true_answer=question["true_answer"],
            category=question["category"],
            subject=question["subject"]
        )

    return f"{len(questions)} ta savol muvaffaqiyatli qayta ishlangan!"
