from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import BotUser
from .serializers import BotUserSerializer
from rest_framework import status
from .models import ChannelStats
from .serializers import ChannelStatsSerializer

class CheckUserAPIView(APIView):
    permission_classes = [AllowAny]
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
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BotUserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BotAllDatesAPIView(APIView):
    def get(self, request):
        all_users = BotUser.objects.all()  # Barcha foydalanuvchilarni olish
        serializer = BotUserSerializer(all_users, many=True)  # Ko‘p obyektlar bo‘lgani uchun many=True
        return Response(serializer.data)  # JSON formatda qaytarish
    
class ChannelStatsView(APIView):
    """
    Kanal statistikalarini qabul qilish va yangilash APIsi
    """

    def get(self, request):
        """Kanal ma’lumotlarini ko‘rsatish"""
        stats = ChannelStats.objects.all()
        serializer = ChannelStatsSerializer(stats, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Kanal ma’lumotlarini qabul qilish va yangilash"""
        data = request.data
        channel_id = data.get("channel_id")

        if not channel_id:
            return Response({"error": "channel_id talab qilinadi"}, status=status.HTTP_400_BAD_REQUEST)

        # Kanal mavjudligini tekshiramiz
        try:
            channel_stats = ChannelStats.objects.get(channel_id=channel_id)
            serializer = ChannelStatsSerializer(channel_stats, data=data, partial=True)
        except ChannelStats.DoesNotExist:
            serializer = ChannelStatsSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)