# app/main.py
from fastapi import FastAPI, File, UploadFile, HTTPException
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from fastapi.middleware.cors import CORSMiddleware
import uuid
from dotenv import load_dotenv
import os

app = FastAPI()
# CORS middleware sozlamalari
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Bu yerda barcha domenlarga ruxsat beriladi ("*" hamma uchun)
    allow_credentials=True,
    allow_methods=["*"],  # Barcha methodlarga (GET, POST, va h.k.) ruxsat beriladi
    allow_headers=["*"],  # Barcha headerslarga ruxsat beriladi
)


# S3 sozlamalari
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")

# S3 clientni sozlash
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=S3_REGION
)
def upload_file_to_s3(file, file_name):
    
    try:
        # Faylni S3 bucket'ga yuklash
        s3_client.upload_fileobj(
            Fileobj=file,
            Bucket=S3_BUCKET_NAME,
            Key=file_name,
            ExtraArgs={"ACL": "public-read"}  # Faylni ochiq qilish uchun
        )

        # Yuklangan faylning URL manzilini qaytarish
        file_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{file_name}"
        return file_url

    except NoCredentialsError:
        raise HTTPException(status_code=500, detail="AWS kredentiallari topilmadi!")
    except PartialCredentialsError:
        raise HTTPException(status_code=500, detail="AWS kredentiallari to'liq emas!")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Xatolik yuz berdi: {str(e)}")

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    
    # Fayl nomini aniqlash (UUID bilan unikallik)
    file_name = f"{uuid.uuid4()}-{file.filename}"

    try:
        # Faylni yuklash uchun S3'ga jo'natish
        file_url = upload_file_to_s3(file.file, file_name)
        return {"message": "Fayl muvaffaqiyatli yuklandi", "file_url": file_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Faylni yuklashda xatolik yuz berdi: {str(e)}")