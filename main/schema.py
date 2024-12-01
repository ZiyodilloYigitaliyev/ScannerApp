import zipfile
from io import BytesIO
from django.core.files.storage import default_storage
from graphene import ObjectType, Mutation, String, Field
from graphene_file_upload.scalars import Upload
from .models import UploadedFile

class UploadZipMutation(Mutation):
    class Arguments:
        file = Upload(required=True)

    success = String()
    message = String()

    def mutate(self, info, file, **kwargs):
        try:
            # Faylni RAM ga yuklash
            zip_file = zipfile.ZipFile(file)

            # PDF fayllarini ZIP faylidan chiqarish va S3'ga yuklash
            for name in zip_file.namelist():
                if name.endswith(".pdf"):
                    # PDF faylini ochish
                    pdf_file = zip_file.open(name)

                    # Faylni S3'ga yuklash
                    s3_path = f"pdf_files/{name}"
                    file_content = pdf_file.read()
                    s3_url = default_storage.save(s3_path, BytesIO(file_content))  # Faylni S3'ga saqlash

                    # Ma'lumotni bazaga saqlash
                    UploadedFile.objects.create(name=name, s3_url=s3_url)

            return UploadZipMutation(success="true", message="Files uploaded successfully!")

        except Exception as e:
            return UploadZipMutation(success="false", message=str(e))

class Mutation(ObjectType):
    upload_zip = UploadZipMutation.Field()
