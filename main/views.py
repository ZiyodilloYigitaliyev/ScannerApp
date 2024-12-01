import zipfile
from io import BytesIO
from django.core.files.storage import default_storage
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import UploadedFile

class UploadZipView(APIView):

    def post(self, request, *args, **kwargs):
        try:
            # ZIP faylini olish
            file = request.FILES['file']
            zip_file = zipfile.ZipFile(file)

            # ZIP faylidan PDF fayllarini chiqarib olish
            for name in zip_file.namelist():
                if name.endswith(".pdf"):
                    # PDF faylini ochish
                    pdf_file = zip_file.open(name)

                    # Faylni S3'ga yuklash
                    s3_path = f"pdf_files/{name}"
                    file_content = pdf_file.read()
                    file_io = BytesIO(file_content)
                    s3_url = default_storage.save(s3_path, file_io)  # Faylni S3'ga saqlash

                    # Faylga public-read ruxsatini o'rnatish
                    default_storage.url(s3_url)  # Faylga URL olish
                    # Faylni "public-read" bilan yuklash
                    uploaded_file_url = f"https://{AWS_S3_CUSTOM_DOMAIN}/{s3_url}"

                    # Ma'lumotni bazaga saqlash
                    UploadedFile.objects.create(name=name, s3_url=uploaded_file_url)

            return Response({"success": "true", "message": "Files uploaded successfully!"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"success": "false", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
