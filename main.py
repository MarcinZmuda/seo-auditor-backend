# ================================================================
# main.py — Główny backend FastAPI (SEO Auditor + Firestore)
# Wersja: 1.2.1 — kompatybilna z Render i FIREBASE_CREDS_JSON
# ================================================================

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
import json

# Wczytaj zmienne .env (dla lokalnego środowiska)
from dotenv import load_dotenv
load_dotenv()

# Tworzy tabele w bazie danych przy starcie aplikacji
database.create_tables() 

app = FastAPI(title="SEO Auditor Backend", version="1.2.1")

# ---------------------------------------------------------------
# 🔧 Etap 1: Konfiguracja klienta D4SEO (HTTPX)
# ---------------------------------------------------------------
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

# ---------------------------------------------------------------
# 🔧 Etap 2: Inicjalizacja Firestore z ENV JSON (Render-friendly)
# ---------------------------------------------------------------
from firebase_admin import credentials, firestore
import firebase_admin

# Ta instancja 'db' będzie JEDYNĄ instancją w całej aplikacji
db = None

try:
    if os.getenv("FIREBASE_CREDS_JSON"):
        creds_json = os.getenv("FIREBASE_CREDS_JSON")
        creds_path = "/tmp/firebase-key.json"
        with open(creds_path, "w") as f:
            f.write(creds_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
        print("✅ FIREBASE_CREDS_JSON zapisany do /tmp/firebase-key.json")

    if not firebase_admin._apps:
        cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        firebase_admin.initialize_app(cred)
        print("✅ Firebase zainicjalizowany poprawnie.")
    else:
        print("ℹ️ Firebase już był zainicjalizowany wcześniej.")

    db = firestore.client() # <--- Jedyna, główna instancja bazy Firestore
    print("✅ Firestore client aktywny.")
except Exception as e:
    db = None
    print(f"❌ Błąd inicjalizacji Firestore: {e}")

# ---------------------------------------------------------------
# 🔧 Etap 3: Endpointy audytu SEO (D4SEO + DB)
# ---------------------------------------------------------------
@app.post("/start-audit")
async def start_audit_endpoint(
    request: StartAuditRequest, 
    db_session: Session = Depends(database.get_db)
):
    """Endpoint dla GPT: Uruchom nowy audyt."""
    domain = request.domain
    
    try:
        job = crud.create_job(db=db_session, domain=domain)
        job_id = job.job_id

        onpage_task_id = await d4seo_client.start_onpage_task(domain, job_id)
        lighthouse_task_id = await d4seo_client.start_lighthouse_task(domain, job_id)

        crud.update_job(db_session, job_id, {
            "onpage_task_id": onpage_task_id,
            "lighthouse_task_id": lighthouse_task_id
        })

        print(f"[{job_id}] Pomyślnie uruchomiono zadania dla {domain}.")
        return {"status": "pending", "job_id": job_id}
        
    except Exception as e:
        print(f"[ERROR] /start-audit: {e}")
        if 'job' in locals() and job:
            crud.delete_job(db_session, job.job_id)
        raise HTTPException(status_code=500, detail=f"Failed to start audit: {str(e)}")


@app.get("/webhook/onpage-done")
async def webhook_onpage_done(
    job_id: str = Query(...), 
    db_session: Session = Depends(database.get_db)
):
    """Webhook: On-Page DONE."""
    print(f"[{job_id}] Otrzymano Webhook: On-Page GOTOWY.")
    try:
        crud.update_job(db_session, job_id, {"onpage_status": "completed"})
        return {"status": "ok"}
    except Exception as e:
        print(f"[{job_id}] Błąd Webhooka On-Page: {e}")
        return {"status": "error"}


@app.get("/webhook/lighthouse-done")
async def webhook_lighthouse_done(
    job_id: str = Query(...), 
    db_session: Session = Depends(database.get_db)
):
    """Webhook: Lighthouse DONE."""
    print(f"[{job_id}] Otrzymano Webhook: Lighthouse GOTOWY.")
    try:
        crud.update_job(db_session, job_id, {"lighthouse_status": "completed"})
        return {"status": "ok"}
    except Exception as e:
        print(f"[{job_id}] Błąd Webhooka Lighthouse: {e}")
        return {"status": "error"}


@app.get("/check-audit-status/{job_id}")
async def check_audit_status_endpoint(
    job_id: str, 
    background_tasks: BackgroundTasks,
    db_session: Session = Depends(database.get_db)
):
    """Sprawdza status zadania."""
    job = crud.get_job(db_session, job_id)
    
    if not job:
        return {"status": "error", "message": "Job not found."}

    if job.onpage_status == "error" or job.lighthouse_status == "error":
        return {"status": "error", "message": "Błąd podczas przetwarzania audytu D4SEO."}

    if job.onpage_status == "pending":
        return {"status": "pending", "message": "Skan On-Page (krok 1/2) w toku..."}
        
    if job.lighthouse_status == "pending":
        return {"status": "pending", "message": "Skan Lighthouse (krok 2/2) w toku..."}

    if job.onpage_status == "completed" and job.lighthouse_status == "completed":
        print(f"[{job_id}] Oba zadania gotowe — agregacja wyników...")
        try:
            onpage_summary_data = await d4seo_client.get_onpage_summary(job.onpage_task_id)
            lighthouse_data = await d4seo_client.get_lighthouse_data(job.lighthouse_task_id)
            final_report_data = await aggregation.build_final_report(job, onpage_summary_data, lighthouse_data)
            background_tasks.add_task(crud.delete_job, db_session, job_id)
            return {"status": "completed", "data": final_report_data}
        except Exception as e:
            crud.update_job(db_session, job_id, {"status": "error"})
            return {"status": "error", "message": f"Błąd podczas agregacji: {e}"}

    return {"status": "error", "message": "Nieznany błąd statusu."}

# ---------------------------------------------------------------
# 🔧 Etap 4: Firestore API — integracja z project_routes.py
# ---------------------------------------------------------------
from project_routes import register_project_routes

# === POPRAWKA ===
# Przekazujemy instancję 'db' (utworzoną w Etapie 2)
# do funkcji rejestrującej, aby uniknąć podwójnej inicjalizacji.
if db:
    register_project_routes(app, db)
    print("✅ [DEBUG] Firestore project_routes zarejestrowane poprawnie.")
else:
    print("❌ [BŁĄD] Nie można zarejestrować project_routes, ponieważ Firestore 'db' jest None.")
# === KONIEC POPRAWKI ===


# ---------------------------------------------------------------
# Testowy endpoint
# ---------------------------------------------------------------
@app.get("/")
def read_root():
    return {"Hello": "World"}
