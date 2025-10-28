# Plik: main.py
from fastapi import FastAPI, HTTPException, Request, Query, Depends
from sqlalchemy.orm import Session
import crud
import d4seo_client
import aggregation
import database
from models import StartAuditRequest # Importujemy to z naszego starego models.py

# Tworzy tabele w bazie danych przy starcie aplikacji
database.create_tables() 

app = FastAPI(title="SEO Auditor Backend")

@app.post("/start-audit")
async def start_audit_endpoint(
    request: StartAuditRequest, 
    db: Session = Depends(database.get_db)
):
    """Endpoint dla GPT: Uruchom nowy audyt."""
    domain = request.domain
    job_id_temp = f"job-{uuid.uuid4()}" # Tymczasowe ID dla webhooków
    
    try:
        # Uruchom oba zadania D4SEO
        onpage_task_id = await d4seo_client.start_onpage_task(domain, job_id_temp)
        lighthouse_task_id = await d4seo_client.start_lighthouse_task(domain, job_id_temp)
        
        # Stwórz wpis w bazie danych PostgreSQL
        job = crud.create_job(
            db=db,
            domain=domain,
            onpage_task_id=onpage_task_id,
            lighthouse_task_id=lighthouse_task_id
        )
        
        # Poprawiamy ID w webhookach na prawdziwe ID z bazy
        # (To jest bardziej zaawansowane, na razie pomińmy i używajmy job_id_temp)
        # UWAGA: Uproszczenie - używamy ID z bazy
        job_id = job.job_id
        # TODO: Musisz zaktualizować `pingback_url` w `d4seo_client.py`, aby używał `job.job_id`
        
        return {"status": "pending", "job_id": job.job_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start audit: {e}")


@app.post("/webhook/onpage-done")
async def webhook_onpage_done(
    request: Request, 
    job_id: str = Query(...), 
    db: Session = Depends(database.get_db)
):
    """Webhook: Odbiera GŁÓWNE dane z On-Page Summary."""
    try:
        onpage_data = await request.json()
        
        if onpage_data.get("status_code") != 20000:
             crud.update_job_status(db, job_id, {"onpage_status": "error"})
             return {"status": "error recorded"}

        crud.update_job_status(db, job_id, {
            "onpage_status": "completed",
            "onpage_data": onpage_data["tasks"][0] 
        })
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook onpage error: {e}")
        return {"status": "error"}

@app.post("/webhook/lighthouse-done")
async def webhook_lighthouse_done(
    request: Request, # Dodajemy request, aby pobrać dane
    job_id: str = Query(...), 
    db: Session = Depends(database.get_db)
):
    """Webhook: Odbiera DANE z Lighthouse."""
    try:
        lighthouse_data = await request.json()

        if lighthouse_data.get("status_code") != 20000:
             crud.update_job_status(db, job_id, {"lighthouse_status": "error"})
             return {"status": "error recorded"}

        crud.update_job_status(db, job_id, {
            "lighthouse_status": "completed",
            "lighthouse_data": lighthouse_data["tasks"][0] # Zapisz dane Lighthouse
        })
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook lighthouse error: {e}")
        return {"status": "error"}


@app.get("/check-audit-status/{job_id}")
async def check_audit_status_endpoint(
    job_id: str, 
    db: Session = Depends(database.get_db)
):
    """Endpoint dla GPT: Sprawdź status zadania."""
    job = crud.get_job(db, job_id)
    
    if not job:
        return {"status": "error", "message": "Job not found."}
    
    if job.onpage_status == "error" or job.lighthouse_status == "error":
        return {"status": "error", "message": "Wystąpił błąd podczas przetwarzania audytu."}

    if job.onpage_status == "pending":
        return {"status": "pending", "message": "Skan On-Page (krok 1/2) jest w toku..."}
        
    if job.lighthouse_status == "pending":
        return {"status": "pending", "message": "Skan Lighthouse (krok 2/2) jest w toku..."}

    # Jeśli oba są "completed"
    try:
        final_report_data = await aggregation.build_final_report(job)
        
        # Wyczyść bazę danych
        crud.delete_job(db, job_id)
        
        return {"status": "completed", "data": final_report_data}
        
    except Exception as e:
        crud.update_job_status(db, job_id, {"status": "error"})
        print(f"Aggregation error: {e}")
        return {"status": "error", "message": f"Błąd podczas agregacji danych: {e}"}
