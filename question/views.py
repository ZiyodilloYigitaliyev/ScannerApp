from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import QuestionList, Question
from .serializers import QuestionSerializer, QuestionListSerializer
import random
import re

# APIView
class GenerateRandomQuestionsView(APIView):
    def get(self, request):
        try:
            # Barcha QuestionList obyektlarini olish
            question_lists = QuestionList.objects.prefetch_related('questions').all()
            serializer = QuestionListSerializer(question_lists, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        try:
             # JSON ma'lumotni to'g'rilash
            if isinstance(request.data, list):
                # List ichidagi birinchi elementni olish
                request_data = request.data[0]
            else:
                request_data = request.data
            questions_num = request_data.get('num', {})
            questions_data = request_data.get('data', {})
            additional_value = questions_num.get('additional_value')
            # Majburiy va boshqa fanlar
            majburiy_fan_1 = questions_data.get('Majburiy_Fan_1', [])
            majburiy_fan_2 = questions_data.get('Majburiy_Fan_2', [])
            majburiy_fan_3 = questions_data.get('Majburiy_Fan_3', [])
            fan_1 = questions_data.get('Fan_1', [])
            fan_2 = questions_data.get('Fan_2', [])

            final_lists = []

            for _ in range(additional_value):
                new_list = {
                    "Majburiy_Fan_1": self.clean_questions(self.get_random_items(majburiy_fan_1, 10)),
                    "Majburiy_Fan_2": self.clean_questions(self.get_random_items(majburiy_fan_2, 10)),
                    "Majburiy_Fan_3": self.clean_questions(self.get_random_items(majburiy_fan_3, 10)),
                    "Fan_1": self.clean_questions(self.get_random_items(fan_1, 30)),
                    "Fan_2": self.clean_questions(self.get_random_items(fan_2, 30)),
                }
                list_id = random.randint(1000, 9999)
                # final_questions - bu yerda ma'lumotni to'plash
                final_questions = {
                    category: [] for category in new_list.keys()
                }
                global_order_counter = 1
                # final_questions'ni to'ldirish
                for category, questions in new_list.items():
                    for i, question in enumerate(questions):
                        final_questions[category].append({
                            "category": category,
                            "subject": question.get("subject", ""),
                            "text": question["text"],
                            "options": question.get("options", ""),
                            "true_answer": question.get("true_answer", ""),
                            "image": question.get("image", None),
                            "order": global_order_counter
                        })
                        global_order_counter += 1
                # final_listsga qo'shish
                final_lists.append({
                    "list_id": list_id,
                    "questions": final_questions
                })
                # Save to database
                try:
                    question_list = QuestionList.objects.create(list_id=list_id)
                    for category, questions in final_questions.items():
                        for question in questions:
                            Question.objects.create(
                                list=question_list,
                                category=category,
                                subject=question.get('subject', ""),
                                text=question.get('text', ""),
                                options=question.get('options', ""),
                                image=question.get('image', None),
                                question_id=question.get('order'),
                                true_answer=question.get('true_answer', "")  # String qiymatni saqlash
                            )
                except Exception as e:
                    print(f"Error during database save: {e}")
                    return Response({"error": "Database save error"}, status=status.HTTP_400_BAD_REQUEST)


            return Response(status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def get_random_items(source_list, count):
        if not source_list:
            return []
        count = min(count, len(source_list))
        return random.sample(source_list, count)

    @staticmethod
    def clean_questions(questions):
        """Savollarning matnini tozalaydi."""
        for question in questions:
            question['text'] = re.sub(r'^\d+\.\s*', '', question['text'])
        return questions