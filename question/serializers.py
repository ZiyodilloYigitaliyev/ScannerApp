from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import RandomData, TrueAnswer

# Serializer yaratish
class RandomDataSerializer(ModelSerializer):
    class Meta:
        model = RandomData
        fields = '__all__'

class TrueAnswerSerializer(serializers.ModelSerializer):
    random_number = serializers.IntegerField(source='random_number.random_number')
    class Meta:
        model = TrueAnswer
        fields = '__all__'
