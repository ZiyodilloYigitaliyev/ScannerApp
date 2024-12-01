from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

class StaticStorage(S3Boto3Storage):
    location = settings.AWS_STATIC_LOCATION

STATICFILES_LOCATION = 'static'
STATICFILES_STORAGE = 'custom_storages.StaticStorage' 


class MediaStorage(S3Boto3Storage):
    location = settings.AWS_MEDIA_LOCATION

MEDIAFILES_LOCATION = 'media'
DEFAULT_FILE_STORAGE = 'custom_storages.MediaStorage'    