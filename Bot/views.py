from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import BotUser
from .serializers import BotUserSerializer


class CheckUserAPIView(APIView):
    """
    Foydalanuvchini tekshirish uchun API.
    """

    def get(self, request):
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({"error": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = BotUser.objects.get(user_id=user_id)
            serializer = BotUserSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except BotUser.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)


class RegisterUserAPIView(APIView):
    """
    Foydalanuvchini ro'yxatdan o'tkazish uchun API.
    """

    def post(self, request):
        serializer = BotUserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

