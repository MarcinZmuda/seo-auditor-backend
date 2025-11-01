# ================================================================
# Plik: project_routes.py (POPRAWIONA WERSJA)
# ================================================================

from fastapi import APIRouter, Request, Depends
from firebase_admin import firestore
import os

router = APIRouter(prefix="/api/projects", tags=["projects"])

# === USUNIĘTO CAŁĄ SEKCJĘ 'init_firestore()' ===
# ...
# ...

# === DODAJEMY TĘ SEKCJĘ ===
# Ta funkcja będzie "pomostem" przekazującym instancję 'db' z main.py
# (gdzie została poprawnie zainicjalizowana) do naszych endpointów poniżej.
_db_instance = None
def get_firestore_db():
    global _db_instance
    if _db_instance is None:
        raise Exception("Błąd krytyczny: Instancja Firestore DB (db) nie została przekazana z main.py do project_routes.")
    return _db_instance
# === KONIEC NOWEJ SEKCJI ===


# ---------------------------------------------------------------
# 📦 Endpoint: dodaj nowy projekt
# ---------------------------------------------------------------
@router.post("/")
async def add_project(
    request: Request,
    # Używamy Depends, aby automatycznie "wstrzyknąć" instancję db
    firestore_client: firestore.Client = Depends(get_firestore_db)
):
    data = await request.json()
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
async def test_firestore(
    # Używamy Depends, aby automatycznie "wstrzyknąć" instancję db
    firestore_client: firestore.Client = Depends(get_firestore_db)
):
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
def register_project_routes(app, db_instance: firestore.Client):
    """
    Ta funkcja jest wywoływana przez main.py przy starcie aplikacji.
    Zapisuje przekazaną instancję 'db' w naszej globalnej zmiennej.
    """
    global _db_instance
    _db_instance = db_instance
    
    app.include_router(router)
    print("✅ [DEBUG] Zarejestrowano project_routes (FastAPI mode)")
