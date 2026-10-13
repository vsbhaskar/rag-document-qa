from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app import config

# pool_pre_ping / pool_recycle: MySQL closes idle connections, so test them before reuse
connect_args = {"check_same_thread": False} if str(config.DATABASE_URL).startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, connect_args=connect_args,
                       pool_pre_ping=True, pool_recycle=280)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()