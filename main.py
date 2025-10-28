from fastapi import FastAPI, HTTPException, Request, Query
from models import StartAuditRequest, JobData
import db
import d4seo_client
import aggregation
import uuid

app = FastAPI(title="SEO Auditor Backend")

@app.post("/start-audit")
async def start_audit_endpoint(request: StartAuditRequest):
    """Endpoint dla GPT: Uruchom nowy audyt."""
    job_id = f"job-{uuid.uuid4()}"
    domain = request.domain
    
    try:
        # Uruchom oba zadania D4SEO
        onpage_task_id = await d4seo_client.start_onpage_task(domain, job_id)
        lighthouse_task_id = await d4seo_client.start_lighthouse_task(domain, job_id)
        
        # Stwórz wpis w bazie Redis
        job_data = JobData(
            job_id=job_id,
            domain=domain,
            onpage_task_id=onpage_task_id,
            lighthouse_task_id=lighthouse_task_id
        )
        db.create_job(job_data)
        
        return {"status": "pending", "job_id": job_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start audit: {e}")


@app.post("/webhook/onpage-done")
async def webhook_onpage_done(request: Request, job_id: str = Query(...)):
    """Webhook: Odbiera GŁÓWNE dane z On-Page Summary."""
    try:
        onpage_data = await request.json()
        
        # Sprawdź, czy zadanie D4SEO się powiodło
        if onpage_data.get("status_code") != 20000:
             db.update_job(job_id, {"onpage_status": "error"})
             return {"status": "error recorded"}

        # Zapisz dane i oznacz jako gotowe
        db.update_job(job_id, {
            "onpage_status": "completed",
            "onpage_data": onpage_data["tasks"][0] # Zapisz tylko dane zadania
        })
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook onpage error: {e}")
        return {"status": "error"}

@app.post("/webhook/lighthouse-done")
async def webhook_lighthouse_done(job_id: str = Query(...)):
    """Webhook: Odbiera POWIADOMIENIE o zakończeniu Lighthouse."""
    try:
        db.update_job(job_id, {"lighthouse_status": "completed"})
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook lighthouse error: {e}")
        return {"status": "error"}


@app.get("/check-audit-status/{job_id}")
async def check_audit_status_endpoint(job_id: str):
    """Endpoint dla GPT: Sprawdź status zadania."""
    job = db.get_job(job_id)
    
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
        # To jest moment, w którym dzieje się magia
        final_report_data = await aggregation.build_final_report(job)
        
        # Wyczyść bazę danych po pomyślnym pobraniu
        db.delete_job(job_id)
        
        return {"status": "completed", "data": final_report_data}
        
    except Exception as e:
        # Jeśli agregacja się nie uda, oznacz zadanie jako błędne
        db.update_job(job_id, {"status": "error"})
        print(f"Aggregation error: {e}")
        return {"status": "error", "message": f"Błąd podczas agregacji danych: {e}"}
