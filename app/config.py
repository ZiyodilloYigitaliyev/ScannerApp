# app/config.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:admin@localhost/postgres"
    SECRET_KEY: str = "qwst23$hfgrt@ldfs/sdkfjrt1d25h/hgfrtdew21jh/"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

settings = Settings()

