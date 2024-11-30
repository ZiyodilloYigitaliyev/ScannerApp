# app/main.py
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.routers.uploadScan import router

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


app.include_router(router,  prefix="/files", tags=["files"])

@app.get("/")
def read_root():
    return {"message": "Start app"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)