import json
import os
from django.http import JsonResponse
from rest_framework.views import APIView
from django.conf import settings
from .models import ProcessedData  # Modelga mos nomni ishlating
from rest_framework.permissions import AllowAny

class ProcessImageView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = ScannedDataSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()  # Save the validated data to the database
            return Response({"message": "Data saved successfully!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



