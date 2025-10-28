# Plik: database.py
import os
from sqlalchemy import create_engine, Column, String, JSON, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import datetime

# Render automatycznie poda ten URL jako zmienną środowiskową
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("Nie znaleziono DATABASE_URL. Upewnij się, że baza PostgreSQL jest podłączona.")

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Model naszej bazy danych (zamiast wpisu w Redis)
class AuditJob(Base):
    __tablename__ = "audit_jobs"
    
    job_id = Column(String, primary_key=True, index=True)
    domain = Column(String)
    status = Column(String, default="pending")
    
    onpage_task_id = Column(String)
    onpage_status = Column(String, default="pending")
    
    lighthouse_task_id = Column(String)
    lighthouse_status = Column(String, default="pending")
    
    # Przechowujemy surowe dane jako JSON
    onpage_data = Column(JSON, nullable=True)
    lighthouse_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

def create_tables():
    """Tworzy tabelę w bazie danych, jeśli nie istnieje."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Funkcja pomocnicza do otwierania i zamykania sesji z bazą."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
