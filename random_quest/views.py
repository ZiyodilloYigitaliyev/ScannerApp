from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Question
from .serializers import QuestionSerializer
import random

class RandomizedQuestionsView(APIView):
    def get(self, request):
        
        questions = Question.objects.all() 
        serializer = QuestionSerializer(questions, many=True)
        data = serializer.data
        random.shuffle(data)
        return Response(data)
