from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import QuestionList, Question
from .serializers import QuestionSerializer, QuestionListSerializer
from rest_framework.permissions import AllowAny
import random
import re

class GenerateRandomQuestionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Bazadan oxirgi list_id ni olib, yangisini qaytaradi."""
        last_id_obj, created = QuestionList.objects.get_or_create(id=1)
        next_id = last_id_obj.last_id + 1
        last_id_obj.last_id = next_id
        last_id_obj.save()
        return next_id

    def post(self, request):
        try:
            if isinstance(request.data, list):
                request_data = request.data[0]
            else:
                request_data = request.data
            questions_num = request_data.get('num', {})
            questions_data = request_data.get('data', {})
            additional_value = questions_num.get('additional_value')

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

                list_id = self.get_next_list_id()  # Yangi list_id ni olish
                final_questions = {category: [] for category in new_list.keys()}
                global_order_counter = 1

                for category, questions in new_list.items():
                    for question in questions:
                        final_questions[category].append({
                            "category": category,
                            "subject": question.get("subject", ""),
                            "text": question["text"],
                            "options": question.get("options", ""),
                            "true_answer": question.get("true_answer", ""),
                            "image": question.get("image", None),
                            "order": global_order_counter,
                        })
                        global_order_counter += 1

                final_lists.append({
                    "list_id": list_id,
                    "questions": final_questions
                })

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
                                true_answer=question.get('true_answer', ""),
                            )
                except Exception as e:
                    print(f"Error during database save: {e}")
                    return Response({"error": "Database save error"}, status=status.HTTP_400_BAD_REQUEST)

            return Response(final_lists, status=status.HTTP_201_CREATED)

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
        for question in questions:
            question['text'] = re.sub(r'^\d+\.\s*', '', question['text'])
        return questions
