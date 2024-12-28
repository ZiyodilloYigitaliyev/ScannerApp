from rest_framework import serializers
from .models import ProcessedTest, ProcessedTestResult

class ProcessedTestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessedTestResult
        fields = ['question_id', 'student_answer', 'is_correct']

class ProcessedTestSerializer(serializers.ModelSerializer):
    results = ProcessedTestResultSerializer(many=True, read_only=True)  # results ni olish

    class Meta:
        model = ProcessedTest
        fields = ['student_id', 'image_url', 'results']


class ZipFileSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if not value.name.endswith('.zip'):
            raise serializers.ValidationError("Fayl zip formatida bo'lishi kerak.")
        return value
