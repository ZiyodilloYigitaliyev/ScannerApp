from docx import Document
from django.core.files.base import ContentFile
from .models import Zip, QuestionImage

def extract_questions_with_images_and_save(docx_file, category, subject):
    """
    Word fayldan savollar va rasmlarni o'qib, ma'lumotlar bazasiga saqlaydi.
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

        # Variantlarni qo‘shish
        elif text.startswith(("A)", "B)", "C)", "D)")) and current_question:
            current_question["options"] += text + '\n'

        # Rasmlarni o'qish
        for run in paragraph.runs:
            if run.element.xpath(".//w:drawing"):
                image_parts = run.element.xpath(".//w:blip/@r:embed")

                if image_parts:  # Agar rasm mavjud bo'lsa
                    image_part = image_parts[0]  # Birinchi tasvirni olish
                    
                    # image_part qiymatining None emasligini tekshirish
                    if image_part is not None:
                        image = document.part.related_parts.get(image_part)

                        if image is not None:  # Agar rasm topilsa
                            # Rasmlarni saqlash
                            current_question["images"].append({
                                "filename": f"image_{i}.png",
                                "content": image.blob
                            })
                        else:
                            print(f"Image not found for part: {image_part}")
                    else:
                        print("Image part is None.")
                else:
                    print(f"No image part found in paragraph {i}")

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
