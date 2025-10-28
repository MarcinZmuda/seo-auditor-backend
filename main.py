# Plik: main.py
from fastapi import FastAPI, HTTPException, Request, Query, Depends, BackgroundTasks
from sqlalchemy.orm import Session
import crud
import d4seo_client
import aggregation
import database
from models import StartAuditRequest
import httpx  # <--- BRAKUJĄCY IMPORT
import uuid
import os

# Wczytaj zmienne .env (tylko dla lokalnego developmentu)
from dotenv import load_dotenv
load_dotenv()

# Tworzy tabele w bazie danych przy starcie aplikacji
database.create_tables() 

app = FastAPI(title="SEO Auditor Backend", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    """Konfiguruje klienta HTTPX przy starcie aplikacji."""
    d4seo_client.client = httpx.AsyncClient(
        base_url=d4seo_client.BASE_URL, 
        headers=d4seo_client.HEADERS, 
        timeout=30.0
    )

@app.on_event("shutdown")
async def shutdown_event():
    """Zamyka klienta HTTPX przy zamknięciu aplikacji."""
    await d4seo_client.client.aclose()


@app.post("/start-audit")
async def start_audit_endpoint(
    request: StartAuditRequest, 
    db: Session = Depends(database.get_db)
):
    """Endpoint dla GPT: Uruchom nowy audyt."""
    domain = request.domain
    
    try:
        # 1. Stwórz wpis w bazie, aby uzyskać unikalny job_id
        job = crud.create_job(db=db, domain=domain)
        job_id = job.job_id
        
        # 2. Uruchom zadania D4SEO z prawdziwym job_id w pingback_url
        onpage_task_id = await d4seo_client.start_onpage_task(domain, job_id)
        lighthouse_task_id = await d4seo_client.start_lighthouse_task(domain, job_id)
        
        # 3. Zaktualizuj wpis w bazie o prawdziwe ID zadań D4SEO
        crud.update_job(db, job_id, {
            "onpage_task_id": onpage_task_id,
            "lighthouse_task_id": lighthouse_task_id
        })
        
        print(f"[{job_id}] Pomyślnie uruchomiono zadania dla {domain}.")
        return {"status": "pending", "job_id": job_id}
        
    except Exception as e:
        print(f"[ERROR] /start-audit: {e}")
        # Jeśli coś pójdzie nie tak, usuń tymczasowy wpis
        if 'job' in locals() and job:
            crud.delete_job(db, job.job_id)
        raise HTTPException(status_code=500, detail=f"Failed to start audit: {str(e)}")


@app.post("/webhook/onpage-done")
async def webhook_onpage_done(
    request: Request, 
    job_id: str = Query(...), 
    db: Session = Depends(database.get_db)
):
    """Webhook: Odbiera DANE z On-Page Summary."""
    print(f"[{job_id}] Otrzymano Webhook: On-Page GOTOWY.")
    try:
        onpage_data = await request.json()
        
        if onpage_data.get("status_code") != 20000:
             print(f"[{job_id}] Błąd w webhooku On-Page: {onpage_data.get('status_message')}")
             crud.update_job(db, job_id, {"onpage_status": "error"})
             return {"status": "error recorded"}

        # Zapisz pełne dane summary i oznacz jako gotowe
        crud.update_job(db, job_id, {
            "onpage_status": "completed",
            "onpage_data": onpage_data["tasks"][0] 
        })
        return {"status": "ok"}
    except Exception as e:
        print(f"[{job_id}] KRYTYCZNY BŁĄD Webhooka On-Page: {e}")
        return {"status": "error"}

@app.post("/webhook/lighthouse-done")
async def webhook_lighthouse_done(
    request: Request,
    job_id: str = Query(...), 
    db: Session = Depends(database.get_db)
):
    """Webhook: Odbiera DANE z Lighthouse."""
    print(f"[{job_id}] Otrzymano Webhook: Lighthouse GOTOWY.")
    try:
        lighthouse_data = await request.json()

        if lighthouse_data.get("status_code") != 20000:
             print(f"[{job_id}] Błąd w webhooku Lighthouse: {lighthouse_data.get('status_message')}")
             crud.update_job(db, job_id, {"lighthouse_status": "error"})
             return {"status": "error recorded"}

        # Zapisz pełne dane Lighthouse i oznacz jako gotowe
        crud.update_job(db, job_id, {
            "lighthouse_status": "completed",
            "lighthouse_data": lighthouse_data["tasks"][0] 
        })
        return {"status": "ok"}
    except Exception as e:
        print(f"[{job_id}] KRYTYCZNY BŁĄD Webhooka Lighthouse: {e}")
        return {"status": "error"}


@app.get("/check-audit-status/{job_id}")
async def check_audit_status_endpoint(
    job_id: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db)
):
    """Endpoint dla GPT: Sprawdź status zadania."""
    job = crud.get_job(db, job_id)
    
    if not job:
        print(f"[{job_id}] GPT pyta o nieistniejące zadanie.")
        return {"status": "error", "message": "Job not found."}
    
    if job.onpage_status == "error" or job.lighthouse_status == "error":
        print(f"[{job_id}] Zwracanie błędu do GPT.")
        return {"status": "error", "message": "Wystąpił błąd podczas przetwarzania audytu D4SEO."}

    if job.onpage_status == "pending":
        print(f"[{job_id}] Status: On-Page w toku.")
        return {"status": "pending", "message": "Skan On-Page (krok 1/2) jest w toku..."}
        
    if job.lighthouse_status == "pending":
        print(f"[{job_id}] Status: Lighthouse w toku.")
        return {"status": "pending", "message": "Skan Lighthouse (krok 2/2) jest w toku..."}

    # Jeśli oba są "completed"
    if job.onpage_status == "completed" and job.lighthouse_status == "completed":
        print(f"[{job_id}] Oba zadania gotowe. Rozpoczynanie agregacji...")
        try:
            # Sprawdź, czy dane istnieją, zanim zaczniesz agregację
            if not job.onpage_data or not job.lighthouse_data:
                print(f"[{job_id}] BŁĄD: Status 'completed', ale brak danych w bazie.")
                return {"status": "error", "message": "Błąd wewnętrzny: brak danych do agregacji."}

            final_report_data = await aggregation.build_final_report(job)
            
            # Usuń zadanie z bazy w tle, aby nie blokować odpowiedzi do GPT
            background_tasks.add_task(crud.delete_job, db, job_id)
            
            print(f"[{job_id}] Agregacja zakończona. Zwracanie pełnych danych do GPT.")
            return {"status": "completed", "data": final_report_data}
            
        except Exception as e:
            # Jeśli agregacja się nie uda, oznacz zadanie jako błędne
            print(f"[{job_id}] KRYTYCZNY BŁĄD agregacji: {e}")
            crud.update_job(db, job_id, {"status": "error"})
            return {"status": "error", "message": f"Błąd podczas agregacji danych: {e}"}

    return {"status": "error", "message": "Nieznany błąd statusu."}

# Endpoint testowy, aby sprawdzić, czy serwer działa
@app.get("/")
def read_root():
    return {"Hello": "World"}
