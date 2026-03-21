"""
Database configuration using SQLAlchemy

FIX #1: Default DB name was incorrect — corrected to 'ca_system'
FIX #2: Added pool_pre_ping, pool_recycle, pool_size for production resilience
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend/ directory (works regardless of cwd)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:cms123@localhost:5432/ca_system"  # FIXED: was wrong DB name
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,    # FIXED: reconnects on stale connections after DB restart
    pool_recycle=1800,     # FIXED: recycle connections every 30 min (avoids timeout errors)
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency to get DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
