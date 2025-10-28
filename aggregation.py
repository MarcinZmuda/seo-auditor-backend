# Plik: aggregation.py
import asyncio
import d4seo_client
from database import AuditJob  # <-- POPRAWNY IMPORT

async def build_final_report(job: AuditJob) -> dict: # <-- UŻYCIE POPRAWNEGO MODELU
    """
    Orkiestrator agregacji. Pobiera wszystkie dane ze wszystkich endpointów D4SEO
    i buduje finalny JSON dla GPT.
    """
    
    print(f"[{job.job_id}] Rozpoczynanie agregacji danych dla: {job.domain}")
    
    # Przechowujemy wszystkie pobrane dane tutaj
    raw_data = {}
    
    # --- Krok 1: Dane bazowe już mamy ---
    # Dane zostały zapisane w bazie przez webhooki
    onpage_task_id = job.onpage_task_id
    lighthouse_task_id = job.lighthouse_task_id
    
    # Sprawdź, czy dane na pewno są w obiekcie job
    if not job.onpage_data or not job.lighthouse_data:
        raise ValueError("Brak danych 'onpage_data' lub 'lighthouse_data' w obiekcie job.")
        
    raw_data["summary"] = job.onpage_data.get("result", [{}])[0]
    raw_data["lighthouse_full"] = job.lighthouse_data.get("result", [{}])[0]


    # --- Krok 2: Uruchom wszystkie zapytania o dane RÓWNOLEGLE ---
    try:
        results = await asyncio.gather(
            # Pomijamy get_onpage_summary i get_lighthouse_data, bo już je mamy
            d4seo_client.get_onpage_pages(onpage_task_id),
            d4seo_client.get_onpage_duplicate_tags(onpage_task_id),
            d4seo_client.get_onpage_links(onpage_task_id),
            d4seo_client.get_onpage_resources(onpage_task_id),
            d4seo_client.get_onpage_non_indexable(onpage_task_id),
            d4seo_client.get_onpage_redirect_chains(onpage_task_id),
            d4seo_client.get_security_headers(job.domain)
            # TODO: Dodaj tutaj resztę wywołań (np. duplicate_content)
        )
        
        # Przypisz wyniki do słownika dla łatwiejszego dostępu
        (
            raw_data["pages"],
            raw_data["duplicate_tags"],
            raw_data["links"],
            raw_data["resources"],
            raw_data["non_indexable"],
            raw_data["redirect_chains"],
            raw_data["security"]
        ) = results
        
    except Exception as e:
        print(f"[{job.job_id}] BŁĄD KRYTYCZNY podczas pobierania danych szczegółowych: {e}")
        raise

    # --- Krok 3: Zbuduj finalny JSON (Mapowanie) ---
    print(f"[{job.job_id}] Mapowanie danych...")
    
    # Skróty do najczęściej używanych danych
    summary_metrics = raw_data["summary"].get("page_metrics", {})
    summary_checks = summary_metrics.get("checks", {})
    lighthouse_items = raw_data["lighthouse_full"].get("items", [{}])[0]
    
    # --- Sekcja 1: Meta-dane ---
    meta_findings = {
        "longTitles": summary_checks.get("title_too_long", 0),
        "shortTitles": summary_checks.get("title_too_short", 0),
        "missingDescriptions": summary_checks.get("no_description", 0),
        "duplicateDescriptions": summary_metrics.get("duplicate_description", 0)
    }
    meta_examples = [
        {"url": item["url"], "issue": f"Zduplikowany tytuł: '{item['title']}'"}
        for item in raw_data["duplicate_tags"].get("items", []) 
        if item.get("tag") == "title"
    ][:3] # Weź 3 przykłady
    # TODO: Dodaj przykłady dla "brakującego opisu" z `raw_data["pages"]`

    # --- Sekcja 11: Wydajność ---
    perf_findings = {
        "lcp": lighthouse_items.get("lcp", {}).get("displayValue", "N/A"),
        "cls": lighthouse_items.get("cls", {}).get("displayValue", "N/A"),
        "mainThreadBlocked": lighthouse_items.get("total_blocking_time", {}).get("displayValue", "N/A"),
        "unusedJsKiB": int(lighthouse_items.get("unused_javascript", {}).get("details", {}).get("overallSavingsKiB", 0)),
        "largeImageKiB": int(lighthouse_items.get("uses_optimized_images", {}).get("details", {}).get("overallSavingsKiB", 0))
    }
    perf_examples = [
        {"url": item["url"], "issue": "Zasób blokujący renderowanie"}
        for item in lighthouse_items.get("render_blocking_resources", {}).get("details", {}).get("items", [])
    ][:3]

    # --- Składanie finalnego raportu ---
    final_report = {
        "auditMetadata": {
            "domain": job.domain,
            "crawlTimestamp": raw_data["summary"].get("domain_info", {}).get("crawl_end"),
            "totalUrlsCrawled": raw_data["summary"].get("total_pages"),
            "cms": raw_data["summary"].get("domain_info", {}).get("cms")
        },
        "metaData": {
            "status": "do_poprawy" if any(v > 0 for v in meta_findings.values()) else "poprawny",
            "summary": "Wykryto problemy z meta danymi, w tym brakujące opisy i zduplikowane tytuły.", # TODO: Uczyń to dynamicznym
            "findings": meta_findings,
            "examples": meta_examples
        },
        "headings": {
            "status": "do_sprawdzenia",
            "summary": "TODO: Uzupełnij",
            "findings": {},
            "examples": []
        },
        "content": {
            "status": "do_sprawdzenia",
            "summary": "TODO: Uzupełnij",
            "findings": {},
            "examples": []
        },
        "indexing": {
            "status": "do_sprawdzenia",
            "summary": "TODO: Uzupełnij",
            "findings": {},
            "examples": []
        },
        "sitemap": {
            "status": "do_sprawdzenia",
            "summary": "TODO: Uzupełnij",
            "findings": {},
            "examples": []
        },
        "robotsTxt": {
            "status": "do_sprawdzenia",
            "summary": "TODO: Uzupełnij",
            "findings": {},
            "examples": []
        },
        "redirects": {
            "status": "do_sprawdzenia",
            "summary": "TODO: Uzupełnij",
            "findings": {},
            "examples": []
        },
        "internalLinks": {
            "status": "do_sprawdzenia",
            "summary": "TODO: Uzupełnij",
            "findings": {},
            "examples": []
        },
        "urls": {
            "status": "do_sprawdzenia",
            "summary": "TODO: Uzupełnij",
            "findings": {},
            "examples": []
        },
        "images": {
            "status": "do_sprawdzenia",
            "summary": "TODO: Uzupełnij",
            "findings": {},
            "examples": []
        },
        "performance": {
            "status": "do_poprawy" if lighthouse_items.get("performance", {}).get("score", 1) < 0.9 else "poprawny",
            "summary": f"Wynik wydajności mobilnej to {lighthouse_items.get('performance', {}).get('score', 0) * 100}/100. Kluczowe metryki (LCP: {perf_findings['lcp']}) wymagają optymalizacji.",
            "findings": perf_findings,
            "examples": perf_examples
        },
        "security": {
            "status": "do_poprawy" if not raw_data["security"]["hsts"] else "poprawny",
            "summary": "Brak kluczowych nagłówków bezpieczeństwa, w tym HSTS.", # TODO: Uczyń to dynamicznym
            "findings": raw_data["security"],
            "examples": [
                {"url": f"https://{job.domain}", "issue": "Brak nagłówka Strict-Transport-Security (HSTS)"}
            ] if not raw_data["security"]["hsts"] else []
        }
    }
    
    print(f"[{job.job_id}] Mapowanie zakończone. Zwracanie raportu do GPT.")
    return final_report
