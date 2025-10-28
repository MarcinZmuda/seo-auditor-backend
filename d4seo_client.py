import httpx
import os
import base64
import asyncio

# Pobierz dane logowania z .env (w Render ustawisz je w Environment)
D4SEO_LOGIN = os.environ["D4SEO_LOGIN"]
D4SEO_PASSWORD = os.environ["D4SEO_PASSWORD"]
BASE_URL = "https://api.dataforseo.com/v3"
RENDER_APP_URL = os.environ["RENDER_EXTERNAL_URL"] # Np. https://twoja-apka.onrender.com

# Przygotuj nagłówek autoryzacyjny
auth_header = base64.b64encode(f"{D4SEO_LOGIN}:{D4SEO_PASSWORD}".encode()).decode()
HEADERS = {"Authorization": f"Basic {auth_header}", "Content-Type": "application/json"}

# Używamy klienta asynchronicznego
client = httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=30.0)

async def start_onpage_task(domain: str, job_id: str) -> str:
    """Uruchamia główne zadanie On-Page."""
    post_data = [{
        "target": domain,
        "max_crawl_pages": 1000, # Możesz to skonfigurować
        "enable_javascript": True,
        "load_resources": True,
        "enable_content_parsing": True,
        "pingback_url": f"{RENDER_APP_URL}/webhook/onpage-done?job_id={job_id}"
    }]
    response = await client.post("/on_page/task_post", json=post_data)
    response.raise_for_status() # Zatrzyma, jeśli D4SEO zwróci błąd
    return response.json()["tasks"][0]["id"]

async def start_lighthouse_task(domain: str, job_id: str) -> str:
    """Uruchamia zadanie Lighthouse dla strony głównej."""
    post_data = [{
        "url": f"https://{domain}",
        "for_mobile": True,
        "pingback_url": f"{RENDER_APP_URL}/webhook/lighthouse-done?job_id={job_id}"
    }]
    response = await client.post("/on_page/lighthouse/task_post", json=post_data)
    response.raise_for_status()
    return response.json()["tasks"][0]["id"]

async def get_lighthouse_data(task_id: str) -> dict:
    """Pobiera gotowe dane z Lighthouse."""
    response = await client.get(f"/on_page/lighthouse/task_get/json/{task_id}")
    return response.json()["tasks"][0]["result"][0]

# --- Tu dodajesz resztę funkcji pobierających dane (z `async def`) ---

async def get_onpage_pages(task_id: str) -> dict:
    post_data = [{"id": task_id, "limit": 1000}] # TODO: Dodaj filtry
    response = await client.post("/on_page/pages", json=post_data)
    return response.json()["tasks"][0]["result"][0]

async def get_onpage_duplicate_tags(task_id: str) -> dict:
    post_data = [{"id": task_id, "limit": 50}]
    response = await client.post("/on_page/duplicate_tags", json=post_data)
    return response.json()["tasks"][0]["result"][0]

async def get_onpage_links(task_id: str) -> dict:
    post_data = [{"id": task_id, "limit": 2000}] # TODO: Dodaj filtry
    response = await client.post("/on_page/links", json=post_data)
    return response.json()["tasks"][0]["result"][0]

# ...itd. dla `resources`, `non_indexable`, `redirect_chains`...

async def get_security_headers(domain: str) -> dict:
    """Nasz własny checker nagłówków bezpieczeństwa."""
    try:
        async with httpx.AsyncClient() as secure_client:
            response = await secure_client.head(f"https://{domain}", follow_redirects=True)
            headers = response.headers
            return {
                "hsts": "strict-transport-security" in headers,
                "csp": "content-security-policy" in headers,
                "referrerPolicy": "referrer-policy" in headers
            }
    except Exception:
        return {"hsts": False, "csp": False, "referrerPolicy": False}
