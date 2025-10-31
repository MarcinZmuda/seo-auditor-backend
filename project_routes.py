# --- 🔐 Inicjalizacja Firebase z ENV JSON ---
from firebase_admin import credentials, firestore, initialize_app
import firebase_admin
import json
import os
import tempfile

if not firebase_admin._apps:
    try:
        firebase_env = os.getenv("FIREBASE_CREDS_JSON")

        if not firebase_env:
            raise ValueError("Brak zmiennej środowiskowej FIREBASE_CREDS_JSON")

        # 🔍 Spróbuj sparsować jako JSON
        try:
            creds_dict = json.loads(firebase_env)
        except json.JSONDecodeError:
            # jeśli Render przekazuje string z escapowanymi znakami
            creds_dict = json.loads(firebase_env.replace("'", "\""))

        # 🔧 Tworzymy tymczasowy plik z JSON (bo firebase_admin tego wymaga)
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as temp_file:
            json.dump(creds_dict, temp_file)
            temp_file_path = temp_file.name

        cred = credentials.Certificate(temp_file_path)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase zainicjalizowany poprawnie z ENV JSON")

    except Exception as e:
        print(f"❌ Błąd inicjalizacji Firebase: {e}")
else:
    print("ℹ️ Firebase już był zainicjalizowany wcześniej.")

try:
    db = firestore.client()
    print("✅ Firestore client aktywny.")
except Exception as e:
    db = None
    print(f"❌ Nie udało się połączyć z Firestore: {e}")

# ---------------------------------------------------------------
# 🔧 Funkcja rejestrująca blueprint
# ---------------------------------------------------------------
def register_project_routes(app, _db=None):
    global db
    if _db:
        db = _db
    app.register_blueprint(project_bp)
    print("✅ [DEBUG] Zarejestrowano project_routes (Firestore mode).")
