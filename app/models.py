from sqlalchemy import Column, Integer, String
from app.database import Base

class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, index=True)
    file_url = Column(String, unique=True)
