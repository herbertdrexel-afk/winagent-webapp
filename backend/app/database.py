import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/winagent")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
