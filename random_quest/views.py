from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Question
from .serializers import QuestionSerializer
import random

class RandomizedQuestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        username = request.user.username

        questions = Question.objects.filter(username=username)

        serializer = QuestionSerializer(questions, many=True)
        data = serializer.data

        random.shuffle(data)

        response_data = {username: data}
        return Response(response_data)
