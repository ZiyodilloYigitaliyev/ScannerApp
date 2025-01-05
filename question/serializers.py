from rest_framework import serializers
from .models import QuestionList, Question

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['question_id', 'category', 'subject', 'text', 'options', 'image', 'true_answer']

class QuestionListSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = QuestionList
        fields = ['list_id', 'created_at', 'questions']
