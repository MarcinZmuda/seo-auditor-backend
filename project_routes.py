# ---------------------------------------------------------------
# 🔧 Konfiguracja tras dla projektów (FastAPI)
# ---------------------------------------------------------------

from fastapi import APIRouter, Request
from firebase_admin import firestore
import os

router = APIRouter(prefix="/api/projects", tags=["projects"])

db = None

# ---------------------------------------------------------------
# 🔥 Inicjalizacja Firestore
# ---------------------------------------------------------------
def init_firestore():
    global db
    if db is not None:
        return db

    import firebase_admin
    from firebase_admin import credentials

    try:
        creds_json = os.getenv("FIREBASE_CREDS_JSON")
        if not creds_json:
            print("❌ Brak zmiennej środowiskowej FIREBASE_CREDS_JSON")
            return None

        cred_path = "/tmp/firebase-key.json"
        with open(cred_path, "w") as f:
            f.write(creds_json)

        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase i Firestore zainicjalizowane poprawnie")
        return db

    except Exception as e:
        print(f"❌ Błąd inicjalizacji Firestore: {e}")
        return None


# ---------------------------------------------------------------
# 📦 Endpoint: dodaj nowy projekt
# ---------------------------------------------------------------
@router.post("/")
async def add_project(request: Request):
    data = await request.json()
    firestore_client = init_firestore()
    if not firestore_client:
        return {"status": "error", "message": "Firestore nie działa"}
    try:
        firestore_client.collection("projects").add(data)
        return {"status": "ok", "message": "Projekt zapisany"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------
# 🧪 Endpoint testowy – sprawdzenie połączenia z Firestore
# ---------------------------------------------------------------
@router.get("/test")
async def test_firestore():
    firestore_client = init_firestore()
    if not firestore_client:
        return {"status": "error", "message": "Brak połączenia z Firestore"}
    try:
        test_ref = firestore_client.collection("test_connection").document("ping")
        test_ref.set({"status": "ok"})
        data = test_ref.get().to_dict()
        return {"status": "ok", "firestore_result": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------
# 🔧 Rejestracja tras w aplikacji głównej (FastAPI)
# ---------------------------------------------------------------
def register_project_routes(app):
    app.include_router(router)
    print("✅ [DEBUG] Zarejestrowano project_routes (FastAPI mode)")
