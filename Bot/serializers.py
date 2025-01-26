from rest_framework import serializers
from .models import BotUser

class BotUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotUser
        fields = ['user_id', 'phone_number', 'created_at']
        read_only_fields = ['created_at']
