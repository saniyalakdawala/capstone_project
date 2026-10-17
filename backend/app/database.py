from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import logging
from app.config import settings

logger = logging.getLogger(__name__)

try:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        echo=False
    )
    # Test connection
    with engine.connect() as conn:
        logger.info("Successfully connected to primary PostgreSQL database.")
except Exception as e:
    logger.warning(f"Could not connect to PostgreSQL ({e}). Falling back to SQLite local database.")
    engine = create_engine(
        "sqlite:///./eidt_mumbai.db",
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
