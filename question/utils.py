from django.core.files.base import ContentFile
from .models import QuestionImage, Zip
from docx import Document


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
                    image_part = run.element.xpath(".//w:blip/@r:embed")[0]
                    image = document.part.related_parts[image_part]
                    current_question["images"].append({
                        "filename": f"image_{i}.png",
                        "content": image.blob
                    })

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