# Plik: crud.py
from sqlalchemy.orm import Session
from database import AuditJob
import uuid

def create_job(db: Session, domain: str) -> AuditJob:
    """Tworzy nowy wpis zadania w bazie danych."""
    
    # Generujemy unikalny, losowy ID dla naszego zadania
    job_id = f"job-{uuid.uuid4()}"
    
    new_job = AuditJob(
        job_id=job_id,
        domain=domain,
        # ID zadań D4SEO dodamy za chwilę
        onpage_task_id="temp_onpage", 
        lighthouse_task_id="temp_lh"
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return new_job

def get_job(db: Session, job_id: str) -> AuditJob | None:
    """Pobiera zadanie z bazy po jego ID."""
    return db.query(AuditJob).filter(AuditJob.job_id == job_id).first()

def update_job(db: Session, job_id: str, updates: dict) -> AuditJob:
    """Aktualizuje pola w istniejącym zadaniu (np. status lub ID zadania)."""
    job = get_job(db, job_id)
    if not job:
        raise ValueError(f"Job o ID {job_id} nie istnieje.")
    
    for key, value in updates.items():
        setattr(job, key, value)
        
    db.commit()
    db.refresh(job)
    return job

def delete_job(db: Session, job_id: str):
    """Usuwa zadanie z bazy (np. po pomyślnym zakończeniu)."""
    job = get_job(db, job_id)
    if job:
        db.delete(job)
        db.commit()
