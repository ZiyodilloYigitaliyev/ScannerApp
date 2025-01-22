from django.conf import settings
import boto3
import uuid
from tempfile import NamedTemporaryFile
import os
from concurrent.futures import ThreadPoolExecutor

def upload_image_to_s3(self, image_name, image_data):
            s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME

            file_name, file_extension = os.path.splitext(image_name)
            unique_name = file_name
            s3_key = f"images/{unique_name}{file_extension}"

            while self.check_file_exists_in_s3(s3_client, bucket_name, s3_key):
                unique_name = f"{uuid.uuid4().hex}{file_extension}"
                s3_key = f'images/{unique_name}'

            with NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(image_data)
                temp_file.close()
                s3_client.upload_file(temp_file.name, bucket_name, s3_key)
                os.unlink(temp_file.name)

            return f'https://{bucket_name}.s3.amazonaws.com/{s3_key}'

def upload_images_concurrently(self, images):
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self.upload_image_to_s3, img_name, img_data): img_name for img_name, img_data in images.items()}
            return {future.result(): images[future] for future in futures}
def check_file_exists_in_s3(self, s3_client, bucket_name, s3_key):
        try:
            s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            return True
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                raise