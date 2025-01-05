import requests
from weasyprint import HTML
from io import BytesIO
import io
import zipfile
from weasyprint.images import Image
from math import ceil

def generate_pdf(question_data):
    pdf_files = {}

    for list_item in question_data:
        if isinstance(list_item, dict):  # Bu yerda list_item lug'at ekanligini tekshiramiz
            list_id = list_item.get('list_id')
            questions = list_item.get('questions', [])

            # HTML tarkibni boshlaymiz
            html_content = f"""
                <html>
                    <head>
                        <style>
                            body {{
                                font-family: Arial, sans-serif;
                                line-height: 1.6;
                                margin: 20px;
                            }}
                            h2 {{
                                text-align: center;
                                font-size: 24px;
                                margin-bottom: 20px;
                            }}
                            h3 {{
                                font-size: 18px;
                                margin-top: 10px;
                                color: #333;
                            }}
                            p {{
                                font-size: 14px;
                                margin: 5px 0;
                            }}
                            .subject {{
                                font-size: 20px;
                                font-weight: bold;
                                color: #007bff;
                                margin-top: 30px;
                            }}
                            .options {{
                                margin-left: 20px;
                            }}
                            .option {{
                                margin-bottom: 5px;
                            }}
                            img {{
                                max-width: 100%;
                                height: auto;
                                margin-top: 15px;
                            }}
                        </style>
                    </head>
                    <body>
                        <h2>List ID: {list_id}</h2>
            """

            question_number = 1
            current_subject = None  # Joriy subjectni tekshirish uchun o'zgaruvchi

            for item in questions:
                question_text = item.get('text', 'Savol mavjud emas')
                options = item.get('options', 'Javoblar mavjud emas')
                subject = item.get('subject', 'Fan nomi mavjud emas')
                image_url = item.get('image', None)
                category = item.get('category', 'Kategoriya mavjud emas')

                # Agar subject yoki category o'zgargan bo'lsa, yangi bo'limni qo'shamiz
                if subject != current_subject:
                    current_subject = subject
                    html_content += f"<div class='subject'>{subject} ({category})</div>"

                # Savolni chiqaramiz
                question_text_with_number = f"{question_number}. {question_text}"
                html_content += f"<h3>{question_text_with_number}</h3>"

                # Variantlarni chiqarish
                option_lines = options.split('\n')
                html_content += "<div class='options'>"
                for option in option_lines:
                    html_content += f"<p class='option'>{option.strip()}</p>"
                html_content += "</div>"

                # Rasmni chiqarish
                if image_url:
                    html_content += f'<img src="{image_url}" alt="Savol rasm">'

                question_number += 1

            html_content += "</body></html>"

            # PDF yaratish va uni bytes sifatida saqlash
            pdf = HTML(string=html_content).write_pdf()

            # PDF faylini 'bytes' sifatida saqlash
            pdf_files[f"list_{list_id}_questions.pdf"] = pdf
        else:
            # Noto'g'ri formatdagi elementlarni tekshirish
            print(f"Xato: {list_item} - Bu element lug'at emas, matn ko'rinishidagi ma'lumot.")

    return pdf_files

def get_api_data():
    url = "http://127.0.0.1:8000/api/questions"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None
def create_zip_from_pdfs(pdf_files):
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, pdf_content in pdf_files.items():
            zip_file.writestr(file_name, pdf_content)

    zip_buffer.seek(0)
    return zip_buffer.read()
def create_zip_file(pdf_files):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        for filename, pdf_content in pdf_files.items():
            zf.writestr(filename, pdf_content)
    zip_buffer.seek(0)
    return zip_buffer
