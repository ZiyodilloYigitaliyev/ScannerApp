import requests
import pdfkit
from bs4 import BeautifulSoup
import re
from django.http import HttpResponse

def get_questions_from_api(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def clean_html_and_remove_numbers(html_text, order):
    soup = BeautifulSoup(html_text, "html.parser")
    for text_element in soup.find_all(string=True):
        if text_element.parent.name not in ["img"]:
            cleaned_text = re.sub(r'^\s*\d+[\.\)\:\-]\s*', '', text_element)
            cleaned_text = f"{order}. {cleaned_text}" if order else cleaned_text
            text_element.replace_with(cleaned_text)
    return str(soup)

def generate_html_from_questions(data):
    full_html = """<html><head><meta charset='UTF-8'><style>
    body { font-family: Arial, sans-serif; margin: 10mm; }
    h1 { text-align: center; margin-bottom: 20px; }
    .category-subject { font-weight: bold; font-size: 16px; margin-top: 20px; }
    .question { font-size: 14px; margin-top: 15px; }
    .options { margin-top: 5px; margin-bottom: 20px; margin-left: 10px; }
    </style></head><body>"""
    
    for list_item in data:
        list_id = list_item.get('list_id', 'Noma\'lum ID')
        question_class = list_item.get('question_class', 'Noma\'lum sinf')
        full_html += f"""
        <div style='page-break-before: always; text-align: center;'>
            <h1>Savollar Kitobi</h1>
            <h2>{question_class}-sinflar</h2>
            <h2>Savollar Kitobi raqami: {list_id}</h2>
        </div>
        <div style='page-break-before: always;'></div>
        """
        
        categories = {}
        for q in list_item['questions']:
            key = (q['category'], q['subject'])
            if key not in categories:
                categories[key] = []
            categories[key].append(q)
        
        for (category, subject), questions in categories.items():
            full_html += f"<div class='category-subject'>{category.replace('_', ' ')} ({subject})</div>"
            for question in questions:
                order = question.get('order', '')
                cleaned_text = clean_html_and_remove_numbers(question['text'], order)
                full_html += f'<div class="question">{cleaned_text}</div>'
                options = question.get('options', [])
                if isinstance(options, list):
                    options_html = "<ul>" + "".join([f"<li>{opt}</li>" for opt in options]) + "</ul>"
                else:
                    options_html = str(options)
                full_html += f'<div class="options">{options_html}</div>'
    
    full_html += "</body></html>"
    return full_html

def generate_pdf(html_content):
    options = {
        'page-size': 'A4',
        'encoding': 'UTF-8',
        'margin-top': '10mm',
        'margin-bottom': '10mm',
        'margin-right': '10mm',
        'margin-left': '10mm',
        'enable-local-file-access': '',
    }
    path_to_wkhtmltopdf = r"/app/bin/wkhtmltopdf"
    config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
    pdf = pdfkit.from_string(html_content, False, options=options, configuration=config)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="savollar_kitobchasi.pdf"'
    return response