from rest_framework import serializers
from .models import ProcessedTest, ProcessedTestResult

class ProcessedTestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessedTestResult
        fields = "__all__"

class ProcessedTestSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    bubbles = serializers.ListField(
        child=serializers.ListField(
            child=serializers.IntegerField(),
            min_length=2,
            max_length=2
        ),
        required=True
    )
# class ProcessedTestSerializer(serializers.ModelSerializer):
#     results = ProcessedTestResultSerializer(many=True, read_only=True)
#
#     class Meta:
#         model = ProcessedTest
#         fields = ['file', 'bubbles', 'student_id', 'results']


