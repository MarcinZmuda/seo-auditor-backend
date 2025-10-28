# Plik: d4seo_client.py
import httpx
import os
import base64
import asyncio

# Pobierz dane logowania ze zmiennych środowiskowych
D4SEO_LOGIN = os.environ["D4SEO_LOGIN"]
D4SEO_PASSWORD = os.environ["D4SEO_PASSWORD"]
BASE_URL = "https://api.dataforseo.com/v3"
# Render automatycznie ustawi tę zmienną
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:10000") 

# Przygotuj nagłówek autoryzacyjny raz
auth_string = f"{D4SEO_LOGIN}:{D4SEO_PASSWORD}"
auth_header = base64.b64encode(auth_string.encode()).decode()
HEADERS = {"Authorization": f"Basic {auth_header}", "Content-Type": "application/json"}

# Używamy jednego, globalnego klienta asynchronicznego
client = httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=30.0)

async def start_onpage_task(domain: str, job_id: str) -> str:
    """Uruchamia główne zadanie On-Page."""
    print(f"[{job_id}] Uruchamianie zadania On-Page dla: {domain}")
    post_data = [{
        "target": domain,
        "max_crawl_pages": 1000, # Możesz to zwiększyć
        "enable_javascript": True,
        "load_resources": True,
        "enable_content_parsing": True,
        "pingback_url": f"{RENDER_EXTERNAL_URL}/webhook/onpage-done?job_id={job_id}"
    }]
    response = await client.post("/on_page/task_post", json=post_data)
    response.raise_for_status() # Zatrzyma, jeśli D4SEO zwróci błąd
    task_id = response.json()["tasks"][0]["id"]
    print(f"[{job_id}] Zadanie On-Page uruchomione: {task_id}")
    return task_id

async def start_lighthouse_task(domain: str, job_id: str) -> str:
    """Uruchamia zadanie Lighthouse dla strony głównej."""
    print(f"[{job_id}] Uruchamianie zadania Lighthouse dla: {domain}")
    post_data = [{
        "url": f"https://{domain}",
        "for_mobile": True,
        "pingback_url": f"{RENDER_EXTERNAL_URL}/webhook/lighthouse-done?job_id={job_id}"
    }]
    response = await client.post("/on_page/lighthouse/task_post", json=post_data)
    response.raise_for_status()
    task_id = response.json()["tasks"][0]["id"]
    print(f"[{job_id}] Zadanie Lighthouse uruchomione: {task_id}")
    return task_id

# --- PONIŻEJ FUNKCJE DO POBIERANIA WYNIKÓW (DLA AGREGACJI) ---

async def get_onpage_summary(task_id: str) -> dict:
    """Pobiera główny raport On-Page Summary."""
    print(f"Pobieranie: OnPage Summary (dla {task_id})")
    response = await client.get(f"/on_page/summary/{task_id}")
    response.raise_for_status()
    return response.json()["tasks"][0]["result"][0]

async def get_lighthouse_data(task_id: str) -> dict:
    """Pobiera gotowe dane z Lighthouse."""
    print(f"Pobieranie: Lighthouse data (dla {task_id})")
    response = await client.get(f"/on_page/lighthouse/task_get/json/{task_id}")
    response.raise_for_status()
    return response.json()["tasks"][0]["result"][0]

async def get_onpage_pages(task_id: str, limit: int = 100) -> dict:
    """Pobiera listę wszystkich stron."""
    print(f"Pobieranie: OnPage Pages (limit {limit})")
    post_data = [{"id": task_id, "limit": limit}]
    response = await client.post("/on_page/pages", json=post_data)
    response.raise_for_status()
    return response.json()["tasks"][0]["result"][0]

async def get_onpage_duplicate_tags(task_id: str, limit: int = 50) -> dict:
    """Pobiera przykłady zduplikowanych tagów."""
    print(f"Pobieranie: Duplicate Tags (limit {limit})")
    post_data = [{"id": task_id, "limit": limit}]
    response = await client.post("/on_page/duplicate_tags", json=post_data)
    response.raise_for_status()
    return response.json()["tasks"][0]["result"][0]

async def get_onpage_links(task_id: str, limit: int = 2000) -> dict:
    """Pobiera linki (dla anchor text i stron-sierot)."""
    print(f"Pobieranie: Links (limit {limit})")
    # TODO: Dodaj filtry, aby pobierać tylko linki wewnętrzne
    post_data = [{"id": task_id, "limit": limit}]
    response = await client.post("/on_page/links", json=post_data)
    response.raise_for_status()
    return response.json()["tasks"][0]["result"][0]
    
async def get_onpage_resources(task_id: str, limit: int = 1000) -> dict:
    """Pobiera zasoby (dla obrazków)."""
    print(f"Pobieranie: Resources (limit {limit})")
    post_data = [{"id": task_id, "limit": limit, "filters": ["resource_type", "=", "image"]}]
    response = await client.post("/on_page/resources", json=post_data)
    response.raise_for_status()
    return response.json()["tasks"][0]["result"][0]

async def get_onpage_non_indexable(task_id: str, limit: int = 500) -> dict:
    """Pobiera strony nieindeksowalne."""
    print(f"Pobieranie: Non-Indexable (limit {limit})")
    post_data = [{"id": task_id, "limit": limit}]
    response = await client.post("/on_page/non_indexable", json=post_data)
    response.raise_for_status()
    return response.json()["tasks"][0]["result"][0]

async def get_onpage_redirect_chains(task_id: str, limit: int = 50) -> dict:
    """Pobiera łańcuchy przekierowań."""
    print(f"Pobieranie: Redirect Chains (limit {limit})")
    post_data = [{"id": task_id, "limit": limit}]
    response = await client.post("/on_page/redirect_chains", json=post_data)
    response.raise_for_status()
    return response.json()["tasks"][0]["result"][0]
    
async def get_onpage_content_parsing(task_id: str, url: str) -> dict:
    """Pobiera word_count dla JEDNEJ, konkretnej strony."""
    print(f"Pobieranie: Content Parsing (dla {url})")
    post_data = [{"id": task_id, "url": url}]
    response = await client.post("/on_page/content_parsing", json=post_data)
    response.raise_for_status()
    # Zwraca `items` lub pusty słownik, jeśli brak danych
    items = response.json()["tasks"][0]["result"][0].get("items")
    return items[0] if items else {}

async def get_security_headers(domain: str) -> dict:
    """Nasz własny checker nagłówków bezpieczeństwa (poza D4SEO)."""
    print(f"Pobieranie: Security Headers (dla {domain})")
    try:
        async with httpx.AsyncClient() as secure_client:
            response = await secure_client.head(f"https://{domain}", follow_redirects=True, timeout=10.0)
            headers = response.headers
            return {
                "hsts": "strict-transport-security" in headers,
                "csp": "content-security-policy" in headers,
                "referrerPolicy": "referrer-policy" in headers
            }
    except Exception as e:
        print(f"Błąd sprawdzania security headers: {e}")
        return {"hsts": False, "csp": False, "referrerPolicy": False}
