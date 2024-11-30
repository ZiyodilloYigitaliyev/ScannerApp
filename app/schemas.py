from pydantic import BaseModel
from typing import Optional

class UploadedFileBase(BaseModel):
    file_name: str
    file_url: str

class UploadedFileCreate(UploadedFileBase):
    """ Fayl yuklash uchun ishlatiladigan schema """
    pass

class UploadedFileResponse(UploadedFileBase):
    """ Javob uchun ishlatiladigan schema """
    id: int

    class Config:
        orm_mode = True
