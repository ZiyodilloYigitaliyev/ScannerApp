from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Question
from .serializers import DataSerializer
import random

class RandomizedQuestionsView(APIView):
    def post(self, request):
        serializer = DataSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Ma'lumot muvaffaqiyatli saqlandi!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
