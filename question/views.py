from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import RandomData, TrueAnswer
from .serializers import RandomDataSerializer, TrueAnswerSerializer
import random

# APIView
class SaveRandomDataView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            # Ma'lumotni o'qish
            incoming_data = request.data
            additional_value = incoming_data.get('additionalValue')
            data_items = incoming_data.get('data', {})

            if not additional_value or not data_items:
                return Response({'error': 'additionalValue yoki data yo\'q'}, status=status.HTTP_400_BAD_REQUEST)

            # 4 xonali random son yaratish
            random_number = self.generate_unique_random_number()

            # Ma'lumotlarni random tartibda joylash
            shuffled_keys = list(data_items.keys())
            random.shuffle(shuffled_keys)
            randomized_data = {key: data_items[key] for key in shuffled_keys}

            # Bazaga saqlash
            random_data_instance = RandomData(random_number=random_number, data=randomized_data)
            random_data_instance.save()

            # true_answer ma'lumotlarini saqlash
            for key, value in data_items.items():
                for question in value:
                    question_id = int(question['text'].split('.')[0])
                    true_answer = question['true_answer']
                    true_answer_instance = TrueAnswer(question_id=question_id, true_answer=true_answer)
                    true_answer_instance.save()

            # Javob qaytarish
            serializer = RandomDataSerializer(random_data_instance)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def generate_unique_random_number(self):
        while True:
            random_number = random.randint(1000, 9999)
            if not RandomData.objects.filter(random_number=random_number).exists():
                return random_number
