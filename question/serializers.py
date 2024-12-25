from rest_framework.serializers import ModelSerializer
from .models import RandomData, TrueAnswer

# Serializer yaratish
class RandomDataSerializer(ModelSerializer):
    class Meta:
        model = RandomData
        fields = '__all__'

class TrueAnswerSerializer(ModelSerializer):
    class Meta:
        model = TrueAnswer
        fields = '__all__'
