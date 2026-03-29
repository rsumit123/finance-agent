"""SQLite database setup with SQLAlchemy."""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

SQLITE_URL = os.getenv("DATABASE_URL", "sqlite:///./finance.db")

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Safe column migrations for SQLite (no Alembic)
    _safe_add_columns = [
        "ALTER TABLE expenses ADD COLUMN linked_transaction_id INTEGER",
    ]
    with engine.connect() as conn:
        for sql in _safe_add_columns:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # column already exists
