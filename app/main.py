# app/main.py
from fastapi import FastAPI, File, UploadFile, HTTPException
from .database import database, metadata, engine
from fastapi.middleware.cors import CORSMiddleware
from app.routers.uploadScan import router
import os

metadata.create_all(bind=engine)

app = FastAPI()
# CORS middleware sozlamalari
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Bu yerda barcha domenlarga ruxsat beriladi ("*" hamma uchun)
    allow_credentials=True,
    allow_methods=["*"],  # Barcha methodlarga (GET, POST, va h.k.) ruxsat beriladi
    allow_headers=["*"],  # Barcha headerslarga ruxsat beriladi
)


app.include_router(router,  prefix="/files", tags=["files"])

@app.get("/")
async def root():
    return {"message": "Hello, Heroku!"}