from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from .models import QuestionList, Question

# Serializer yaratish
class QuestionListSerializer(ModelSerializer):
    class Meta:
        model = QuestionList
        fields = '__all__'

class QuestionSerializer(serializers.ModelSerializer):
    random_number = serializers.IntegerField(source='random_number.random_number')
    class Meta:
        model = Question
        fields = '__all__'
