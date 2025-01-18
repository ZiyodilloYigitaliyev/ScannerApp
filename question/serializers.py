from rest_framework import serializers
from .models import QuestionList, Question, Zip

class ZipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zip
        fields = '__all__'

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = '__all__'

class QuestionListSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = QuestionList
        fields = '__all__'
