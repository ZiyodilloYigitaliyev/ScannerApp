from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import QuestionList, Question
from .serializers import QuestionSerializer, QuestionListSerializer
import random

# APIView
class GenerateRandomQuestionsView(APIView):
    def post(self, request):
        try: 
            print(request.data)
            questions_data = request.data            
            # Majburiy va boshqa fanlar
            majburiy_fan_1 = questions_data.get('Majburiy_Fan_1', [])
            majburiy_fan_2 = questions_data.get('Majburiy_Fan_2', [])
            majburiy_fan_3 = questions_data.get('Majburiy_Fan_3', [])
            fan_1 = questions_data.get('Fan_1', [])
            fan_2 = questions_data.get('Fan_2', [])
            additional_value = questions_data.get('additional_value')

            final_lists = []

            for _ in range(additional_value):
                new_list = []

                # Majburiy fanlardan 10 tadan tanlash
                new_list.extend(self.get_random_items(majburiy_fan_1, 10))
                new_list.extend(self.get_random_items(majburiy_fan_2, 10))
                new_list.extend(self.get_random_items(majburiy_fan_3, 10))

                # Fanlardan 30 tadan tanlash
                new_list.extend(self.get_random_items(fan_1, 30))
                new_list.extend(self.get_random_items(fan_2, 30))

                # Tasodifiy ID yaratish
                list_id = random.randint(1000, 9999)

                # Final listga qo'shish 
                final_lists.append({
                    "list_id": list_id,
                    "questions": new_list,
                })

                # Save to database
                question_list = QuestionList.objects.create(list_id=list_id)
                for question in new_list:
                    Question.objects.create(
                        list=question_list,
                        question_id=question.get('id'),
                        true_answer=question.get('true_answer', False)
                    )

            return Response({"final_lists": final_lists}, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def get_random_items(source_list, count):
        if not source_list:
            return []

        # Elementlar sonini moslashtirish
        count = min(count, len(source_list))
        return random.sample(source_list, count)
