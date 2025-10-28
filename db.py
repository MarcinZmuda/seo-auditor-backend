import redis
import json
import os
from models import JobData

# Pobierz URL do Redis z zmiennych środowiskowych Render
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL)

def create_job(job_data: JobData) -> None:
    """Zapisuje nowy job w Redis."""
    # Przechowujemy dane przez 24h
    redis_client.set(f"job:{job_data.job_id}", job_data.model_dump_json(), ex=86400)

def get_job(job_id: str) -> JobData | None:
    """Pobiera job z Redis."""
    data = redis_client.get(f"job:{job_id}")
    if data:
        return JobData(**json.loads(data))
    return None

def update_job(job_id: str, updates: dict) -> JobData:
    """Aktualizuje pola w istniejącym jobie."""
    job_data = get_job(job_id)
    if not job_data:
        raise ValueError("Job not found")
    
    job_data_dict = job_data.model_dump()
    job_data_dict.update(updates)
    
    updated_job_data = JobData(**job_data_dict)
    redis_client.set(f"job:{job_id}", updated_job_data.model_dump_json(), ex=86400)
    return updated_job_data

def delete_job(job_id: str) -> None:
    """Usuwa job po zakończeniu."""
    redis_client.delete(f"job:{job_id}")
