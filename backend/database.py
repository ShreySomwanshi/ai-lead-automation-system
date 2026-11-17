"""
Database configuration and session management using SQLAlchemy.
Uses SQLite for zero-setup, thread-safe, high-performance structured storage.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Database file stored locally in the project backend directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "leads.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Connect args needed for SQLite thread-safety
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for API routes to yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes all database tables."""
    import backend.models  # Ensure models are registered
    Base.metadata.create_all(bind=engine)
    return DB_PATH
