# Plik: project_routes.py
from fastapi import FastAPI, Request, HTTPException
from firebase_admin import credentials, firestore
import firebase_admin
import base64
import uuid
import os

# Inicjalizacja Firestore (Firebase Admin 6.5+)
if not firebase_admin._apps:
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "firebase-key.json")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def register_project_routes(app: FastAPI):

    @app.post("/api/project/create")
    async def create_project(request: Request):
        """Tworzy nowy projekt SEO w Firestore (S2)."""
        data = await request.json()
        topic = data.get("topic", "undefined-topic")

        # Obsługa briefu tekstowego lub Base64
        if "brief_base64" in data:
            try:
                brief_content = base64.b64decode(data["brief_base64"]).decode("utf-8")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Błąd dekodowania Base64: {str(e)}")
        elif "brief_text" in data:
            brief_content = data["brief_text"]
        else:
            raise HTTPException(status_code=400, detail="Missing brief_text or brief_base64")

        try:
            project_id = str(uuid.uuid4())
            doc_ref = db.collection("seo_projects").document(project_id)
            doc_ref.set({
                "project_id": project_id,
                "topic": topic,
                "brief_text": brief_content,
                "keywords_state": {},
                "locked_terms": [],
                "created_at": firestore.SERVER_TIMESTAMP
            })

            return {
                "status": "✅ Projekt utworzony",
                "project_id": project_id,
                "topic": topic,
                "keywords": 0,
                "headers": 0
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Firestore error: {str(e)}")

    # --- Dodawanie batcha (S3)
    @app.post("/api/project/{project_id}/add_batch")
    async def add_batch(project_id: str, request: Request):
        """Dodaje batch treści i aktualizuje liczniki fraz."""
        try:
            text = await request.body()
            text = text.decode("utf-8") if isinstance(text, bytes) else str(text)

            doc_ref = db.collection("seo_projects").document(project_id)
            doc = doc_ref.get()

            if not doc.exists:
                raise HTTPException(status_code=404, detail=f"Projekt {project_id} nie istnieje.")

            data = doc.to_dict()
            keywords_state = data.get("keywords_state", {})

            # Symulacja prostego liczenia fraz
            word_counts = {}
            for word in text.split():
                word = word.strip().lower()
                if len(word) > 2:
                    word_counts[word] = word_counts.get(word, 0) + 1

            # Aktualizacja Firestore
            doc_ref.update({
                "last_batch_text": text,
                "last_batch_length": len(text.split()),
                "keywords_state": word_counts,
                "updated_at": firestore.SERVER_TIMESTAMP
            })

            return {
                "status": "OK",
                "batch_length": len(text.split()),
                "counts": word_counts,
                "report": [f"{k}: {v}" for k, v in word_counts.items()],
                "locked_terms": [],
                "updated_keywords": len(word_counts)
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Błąd dodawania batcha: {str(e)}")

    # --- Usuwanie projektu (S4)
    @app.delete("/api/project/{project_id}")
    async def delete_project(project_id: str):
        """Usuwa projekt SEO i zwraca raport końcowy."""
        try:
            doc_ref = db.collection("seo_projects").document(project_id)
            doc = doc_ref.get()
            if not doc.exists:
                raise HTTPException(status_code=404, detail=f"Projekt {project_id} nie istnieje.")

            data = doc.to_dict()
            doc_ref.delete()

            return {
                "status": f"✅ Projekt {project_id} został usunięty z Firestore.",
                "summary": {
                    "topic": data.get("topic", ""),
                    "total_batches": 1,
                    "total_length": data.get("last_batch_length", 0),
                    "locked_terms_count": len(data.get("locked_terms", [])),
                    "timestamp": str(data.get("created_at"))
                }
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Błąd usuwania projektu: {str(e)}")

    # --- Health check
    @app.get("/api/health")
    async def health_check():
        """Sprawdza status API."""
        return {
            "status": "ok",
            "version": "v6.3.0-hybrid-json",
            "message": "Master SEO API działa poprawnie (pełna integracja z n-gram sources)."
        }
