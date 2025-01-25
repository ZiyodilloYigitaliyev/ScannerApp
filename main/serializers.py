from rest_framework import serializers
from .models import ProcessedTest, ProcessedTestResult

class ProcessedTestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessedTestResult
        fields = "__all__"

class ProcessedTestSerializer(serializers.ModelSerializer):
    results = ProcessedTestResultSerializer(many=True, read_only=True)

    class Meta:
        model = ProcessedTest
        fields = ['file', 'bubbles', 'student_id', 'image_url', 'results']


class ZipFileSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if not value.name.endswith('.zip'):
            raise serializers.ValidationError("Fayl zip formatida bo'lishi kerak.")
        return value
