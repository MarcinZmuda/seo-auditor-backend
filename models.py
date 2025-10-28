# Plik: models.py
import pydantic

class StartAuditRequest(pydantic.BaseModel):
    """
    Schemat danych, których oczekujemy od GPT
    podczas uruchamiania audytu.
    """
    domain: str
