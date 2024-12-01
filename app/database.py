from sqlalchemy import create_engine, MetaData
from databases import Database
from .config import settings

DATABASE_URL = settings.DATABASE_URL
engine = create_engine(DATABASE_URL)
metadata = MetaData()


