import zipfile
import os
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

            for name in zip_file.namelist():
                if name.endswith(".pdf"):
                    # Har bir PDF ni AWS S3 ga yuklash
                    pdf_file = zip_file.open(name)
                    s3_path = f"pdf_files/{name}"
                    s3_url = default_storage.save(s3_path, pdf_file)

                    # Ma'lumotni bazaga saqlash
                    UploadedFile.objects.create(name=name, s3_url=s3_url)

            return UploadZipMutation(success="true", message="Files uploaded successfully!")
        except Exception as e:
            return UploadZipMutation(success="false", message=str(e))

class Mutation(ObjectType):
    upload_zip = UploadZipMutation.Field()
