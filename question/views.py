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
            additional_value = incoming_data.get('additionalValue')  # 4 xonali raqamlar soni
            data_items = incoming_data.get('data', [])  # Savollar ro‘yxati

            if not additional_value or not data_items:
                return Response({'error': 'additionalValue yoki data yo\'q'}, status=status.HTTP_400_BAD_REQUEST)

            # 4 xonali unikal raqamlar yaratish
            random_numbers = self.generate_unique_random_numbers(additional_value)

            # Savollarni random joylashtirish
            randomized_data = random.sample(data_items, len(data_items))

            # Bazaga saqlash: Har bir 4 xonali raqamga tegishli savollarni bog'lash
            for random_number in random_numbers:
                related_questions = randomized_data[:90]  # 90 ta savolni olish
                randomized_data = randomized_data[90:]  # Keyingi savollar uchun ro‘yxatni yangilash

                # RandomData yozuvi
                random_data_instance = RandomData(random_number=random_number, data=related_questions)
                random_data_instance.save()

                # Har bir savolga ID berish va true_answer'ni saqlash
                for index, question in enumerate(related_questions, start=1):
                    question_id = index  # 1 dan 90 gacha ID
                    true_answer = question['true_answer']

                    # TrueAnswer yozuvi
                    true_answer_instance = TrueAnswer(question_id=question_id, true_answer=true_answer)
                    true_answer_instance.save()

            return Response({'message': 'Ma\'lumotlar muvaffaqiyatli saqlandi'}, status=status.HTTP_201_CREATED)

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

