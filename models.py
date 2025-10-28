import pydantic

# Schemat dla danych wejściowych od GPT
class StartAuditRequest(pydantic.BaseModel):
    domain: str

# Schemat danych przechowywanych w Redis
class JobData(pydantic.BaseModel):
    job_id: str
    domain: str
    status: str = "pending"
    onpage_task_id: str
    onpage_status: str = "pending"
    onpage_data: dict | None = None  # Tutaj trafia wynik z Summary
    lighthouse_task_id: str
    lighthouse_status: str = "pending"
    lighthouse_data: dict | None = None # Tutaj trafia wynik z Lighthouse
