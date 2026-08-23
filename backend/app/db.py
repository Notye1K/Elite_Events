from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def initialize_database():
    Base.metadata.create_all(bind=engine)

    event_columns = {
        column["name"] for column in inspect(engine).get_columns("events")
    }
    if "image_url" not in event_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE events ADD COLUMN image_url VARCHAR(500)")
            )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
