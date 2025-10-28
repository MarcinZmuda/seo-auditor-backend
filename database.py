# Plik: database.py
import os
from sqlalchemy import create_engine, Column, String, JSON, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import datetime

# Render automatycznie dostarczy tę zmienną środowiskową,
# gdy połączysz bazę danych z usługą.
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("BŁĄD KRYTYCZNY: Nie znaleziono zmiennej DATABASE_URL.")
    # W trybie lokalnym możesz ustawić domyślny URL, np.:
    # DATABASE_URL = "postgresql://user:password@localhost/seo_auditor_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base to klasa bazowa dla naszych modeli tabel
Base = declarative_base()

class AuditJob(Base):
    """
    Model tabeli 'audit_jobs' w bazie PostgreSQL.
    Będzie śledzić status każdego zadania audytu.
    """
    __tablename__ = "audit_jobs"
    
    # Nasz unikalny identyfikator zadania
    job_id = Column(String, primary_key=True, index=True)
    domain = Column(String)
    
    # Ogólny status zadania (pending, error, completed)
    status = Column(String, default="pending")
    
    # ID i status dla zadania On-Page (główny skan)
    onpage_task_id = Column(String)
    onpage_status = Column(String, default="pending")
    
    # ID i status dla zadania Lighthouse (wydajność)
    lighthouse_task_id = Column(String)
    lighthouse_status = Column(String, default="pending")
    
    # Przechowujemy surowe dane z D4SEO w formacie JSON
    # Uzupełnimy je, gdy webhooki nas powiadomią
    onpage_data = Column(JSON, nullable=True)
    lighthouse_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

def create_tables():
    """Tworzy tabelę w bazie danych przy starcie aplikacji."""
    print("Tworzenie tabel (jeśli nie istnieją)...")
    Base.metadata.create_all(bind=engine)
    print("Tabele gotowe.")

def get_db():
    """
    Funkcja pomocnicza (dependency injection) dla FastAPI.
    Automatycznie otwiera i zamyka sesję z bazą danych
    dla każdego zapytania API.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
