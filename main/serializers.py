from django.forms import FileField, JSONField
from rest_framework import serializers
from rest_framework.serializers import Serializer

from .models import ProcessedTest, ProcessedTestResult

class ProcessedTestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessedTestResult
        fields = "__all__"

class ProcessedTestSerializer(Serializer):
    file = FileField(required=True)  # Fayl maydoni
    bubbles = JSONField(required=True)  # JSON formatidagi ma'lumotlar uchun may
# class ProcessedTestSerializer(serializers.ModelSerializer):
#     results = ProcessedTestResultSerializer(many=True, read_only=True)
#
#     class Meta:
#         model = ProcessedTest
#         fields = ['file', 'bubbles', 'student_id', 'results']


