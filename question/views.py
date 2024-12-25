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
            # Kiruvchi ma'lumotlarni olish
            incoming_data = request.data
            additional_value = incoming_data.get('additionalValue')  # 4 xonali random raqamlar soni
            data_items = incoming_data.get('data', [])  # Savollar ro‘yxati

            if not additional_value or not data_items:
                return Response({'error': 'additionalValue yoki data yo‘q'}, status=status.HTTP_400_BAD_REQUEST)

            # 4 xonali unikal random raqamlar yaratish
            random_numbers = self.generate_unique_random_numbers(additional_value)

            all_random_data = []  # Saqlangan barcha random data ma’lumotlarini yig‘ish uchun
            all_true_answers = []  # Saqlangan barcha true_answer yozuvlari uchun

            # RandomData va TrueAnswer ma'lumotlarini bazaga saqlash
            for random_number in random_numbers:
                # RandomData yozuvi
                random_data_instance = RandomData(random_number=random_number, data=data_items)
                random_data_instance.save()
                all_random_data.append(random_data_instance)

                # TrueAnswer yozuvlarini saqlash
                for item in data_items:
                    question_id = int(item['text'].split('.')[0])  # Savol ID
                    true_answer = item['true_answer']

                    true_answer_instance = TrueAnswer(
                        random_number=random_data_instance,  # ForeignKey orqali bog‘lash
                        question_id=question_id,
                        true_answer=true_answer
                    )
                    true_answer_instance.save()
                    all_true_answers.append(true_answer_instance)


            # RandomData va TrueAnswer serializerlarini qo‘llash
            random_data_serializer = RandomDataSerializer(all_random_data, many=True)
            true_answer_serializer = TrueAnswerSerializer(all_true_answers, many=True)

            return Response({
                'random_data': random_data_serializer.data,
                'true_answers': true_answer_serializer.data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def generate_unique_random_numbers(self, count):
        """
        Berilgan miqdordagi unikal random 4 xonali raqamlarni qaytaradi.
        """
        random_numbers = set()
        while len(random_numbers) < count:
            random_number = random.randint(1000, 9999)
            if random_number not in random_numbers:
                random_numbers.add(random_number)
        return list(random_numbers)