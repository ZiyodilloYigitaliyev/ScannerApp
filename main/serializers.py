from rest_framework import serializers

class ZipFileSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if not value.name.endswith('.zip'):
            raise serializers.ValidationError("Fayl zip formatida bo'lishi kerak.")
        return value
