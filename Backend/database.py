import os
from pathlib import Path
from dotenv import load_dotenv
from sqlmodel import create_engine

load_dotenv(Path(__file__).parent / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///exam_app.db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
