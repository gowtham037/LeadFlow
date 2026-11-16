"""
Database engine + session factory + declarative Base.


- Postgres primary (production / docker-compose)
- SQLite fallback (tests, standalone runs) if Postgres unreachable
- SQLAlchemy 2.0 declarative style
"""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _build_engine():
    """Try Postgres first; fall back to SQLite for tests / standalone."""
    try:
        eng = create_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            echo=settings.db_echo,
            future=True,
        )
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connected to PostgreSQL: %s", settings.database_url.split("@")[-1])
        return eng
    except OperationalError as exc:
        if settings.environment == "test":
            logger.warning("Postgres unreachable in test env — using SQLite fallback")
            return create_engine(
                settings.sqlite_fallback_url,
                echo=settings.db_echo,
                future=True,
                connect_args={"check_same_thread": False},
            )
        logger.error("Postgres unreachable: %s", exc)
        raise


engine = _build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db():
    """FastAPI dependency — yields a DB session, closes it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

