# Plik: main.py
from fastapi import FastAPI, HTTPException, Request, Query, Depends, BackgroundTasks
from sqlalchemy.orm import Session
import crud
import d4seo_client
import aggregation
import database
from models import StartAuditRequest
import httpx
import uuid
import os

# Wczytaj zmienne .env (tylko dla lokalnego developmentu)
from dotenv import load_dotenv
load_dotenv()

# Tworzy tabele w bazie danych przy starcie aplikacji
database.create_tables() 

app = FastAPI(title="SEO Auditor Backend", version="1.2.0") # Podnieśliśmy wersję

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


@app.get("/webhook/onpage-done") # <-- POPRAWKA 1: Zmiana na GET
async def webhook_onpage_done(
    job_id: str = Query(...), 
    db: Session = Depends(database.get_db)
    # Usunięto 'request: Request', bo GET nie ma body
):
    """
    Webhook: Odbiera POWIADOMIENIE o zakończeniu On-Page.
    Nie zapisuje już danych, tylko zmienia status.
    """
    print(f"[{job_id}] Otrzymano Webhook GET: On-Page GOTOWY.")
    try:
        # D4SEO wysyła `status_code` w query params, ale nie musimy go sprawdzać.
        # Jeśli webhook został wywołany, zakładamy, że jest OK.
        # W razie błędu, /check-audit-status i tak go wykryje.
        
        crud.update_job(db, job_id, {
            "onpage_status": "completed"
        })
        return {"status": "ok"}
    except Exception as e:
        print(f"[{job_id}] KRYTYCZNY BŁĄD Webhooka On-Page: {e}")
        return {"status": "error"}

@app.get("/webhook/lighthouse-done") # <-- POPRAWKA 2: Zmiana na GET
async def webhook_lighthouse_done(
    job_id: str = Query(...), 
    db: Session = Depends(database.get_db)
    # Usunięto 'request: Request'
):
    """
    Webhook: Odbiera POWIADOMIENIE o zakończeniu Lighthouse.
    Nie zapisuje już danych, tylko zmienia status.
    """
    print(f"[{job_id}] Otrzymano Webhook GET: Lighthouse GOTOWY.")
    try:
        crud.update_job(db, job_id, {
            "lighthouse_status": "completed"
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

    if job.onpage_status == "completed" and job.lighthouse_status == "completed":
        print(f"[{job_id}] Oba zadania gotowe. Rozpoczynanie agregacji...")
        try:
            # 1. Pobierz surowe dane, których nam brakowało
            print(f"[{job_id}] Pobieranie wyników OnPage Summary...")
            onpage_summary_data = await d4seo_client.get_onpage_summary(job.onpage_task_id)
            
            print(f"[{job_id}] Pobieranie wyników Lighthouse...")
            lighthouse_data = await d4seo_client.get_lighthouse_data(job.lighthouse_task_id)

            # 2. Wywołaj agregację z nowymi danymi
            final_report_data = await aggregation.build_final_report(
                job, 
                onpage_summary_data, 
                lighthouse_data
            )
            
            # 3. Usuń zadanie z bazy w tle
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

# --- 🔗 Integracja z Firestore Master SEO API ---
from firebase_admin import firestore
import firebase_admin
from project_routes import register_project_routes

# Zainicjuj Firestore tylko raz
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()
register_project_routes(app, db)
print("✅ [DEBUG] Firestore project_routes zarejestrowane poprawnie.")

