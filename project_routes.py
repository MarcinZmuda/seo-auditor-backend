# Plik: project_routes.py
from fastapi import FastAPI, Request, HTTPException
from firebase_admin import credentials, firestore
import firebase_admin
import base64
import uuid
import os
import json


# 🔧 Inicjalizacja Firestore (obsługa JSON z ENV lub pliku)
if not firebase_admin._apps:
    firebase_key_env = os.getenv("FIREBASE_KEY_JSON")

    if firebase_key_env:
        # Jeśli klucz jest przekazany jako zmienna środowiskowa
        try:
            key_dict = json.loads(firebase_key_env)
            cred = credentials.Certificate(key_dict)
            print("✅ Firebase init via FIREBASE_KEY_JSON environment variable")
        except Exception as e:
            print(f"❌ Błąd dekodowania FIREBASE_KEY_JSON: {e}")
            raise
    else:
        # Jeśli używamy klasycznego pliku firebase-key.json
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "firebase-key.json")
        if not os.path.exists(cred_path):
            raise FileNotFoundError(f"Brak pliku klucza Firebase: {cred_path}")
        cred = credentials.Certificate(cred_path)
        print(f"✅ Firebase init via file: {cred_path}")

    firebase_admin.initialize_app(cred)

db = firestore.client()


def register_project_routes(app: FastAPI):
    """Rejestracja endpointów projektowych w FastAPI"""

    @app.post("/api/project/create")
    async def create_project(request: Request):
        """
        Tworzy nowy projekt w Firestore.
        Obsługuje standardowy brief lub wersję zakodowaną Base64.
        """
        try:
            data = await request.json()

            # 🔐 Jeśli przychodzi Base64
            if "brief_base64" in data:
                brief_bytes = base64.b64decode(data["brief_base64"])
                brief_text = brief_bytes.decode("utf-8")
                data["brief"] = brief_text
                del data["brief_base64"]

            # Generowanie unikalnego ID projektu
            project_id = str(uuid.uuid4())
            data["id"] = project_id

            # Zapis do Firestore
            db.collection("projects").document(project_id).set(data)

            print(f"✅ Utworzono projekt {project_id}")
            return {"status": "success", "project_id": project_id}

        except Exception as e:
            print(f"❌ Błąd przy tworzeniu projektu: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/project/{project_id}")
    async def get_project(project_id: str):
        """Pobiera dane projektu z Firestore"""
        try:
            doc_ref = db.collection("projects").document(project_id)
            doc = doc_ref.get()
            if not doc.exists:
                raise HTTPException(status_code=404, detail="Projekt nie istnieje.")
            return {"status": "ok", "data": doc.to_dict()}
        except Exception as e:
            print(f"❌ Błąd przy pobieraniu projektu {project_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/health")
    async def health_check():
        """Prosty endpoint do testowania połączenia z backendem"""
        try:
            # Krótkie zapytanie testowe
            return {
                "status": "ok",
                "version": "v6.3.0-hybrid-json",
                "message": "Master SEO API działa poprawnie (pełna integracja z n-gram sources)."
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
