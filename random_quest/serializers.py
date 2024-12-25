from rest_framework import serializers
from .models import Question, Data

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'category', 'subject', 'text', 'options', 'true_answer', 'image']


class DataSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, source='questions')

    class Meta:
        model = Data
        fields = ['additional_value', 'questions']

    def create(self, validated_data):
        questions_data = validated_data.pop('questions')
        data_instance = Data.objects.create(**validated_data)

        for question_data in questions_data:
            question_instance, _ = Question.objects.get_or_create(**question_data)
            data_instance.questions.add(question_instance)

        return data_instance
