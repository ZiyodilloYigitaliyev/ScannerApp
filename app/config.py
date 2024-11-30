# app/config.py
# from pydantic import BaseSettings
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
class Settings(BaseSettings):
    DATABASE_URL: str =  os.getenv("DATABASE_URL")
    SECRET_KEY: str =  os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

settings = Settings()

