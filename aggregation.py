import asyncio
import d4seo_client
from models import JobData

async def build_final_report(job_data: JobData) -> dict:
    """Pobiera wszystkie dane i agreguje je w jeden JSON."""
    
    # Dane bazowe już mamy
    onpage_summary = job_data.onpage_data["result"][0]
    onpage_task_id = job_data.onpage_task_id
    lighthouse_task_id = job_data.lighthouse_task_id
    
    # Krok 1: Uruchom wszystkie zapytania o dane szczegółowe RÓWNOLEGLE
    try:
        (
            lighthouse_data,
            pages_data,
            duplicate_tags_data,
            links_data,
            resources_data,
            non_indexable_data,
            security_data
            # TODO: Dodaj resztę wywołań (redirect_chains, duplicate_content, etc.)
        ) = await asyncio.gather(
            d4seo_client.get_lighthouse_data(lighthouse_task_id),
            d4seo_client.get_onpage_pages(onpage_task_id),
            d4seo_client.get_onpage_duplicate_tags(onpage_task_id),
            d4seo_client.get_onpage_links(onpage_task_id),
            d4seo_client.get_onpage_resources(onpage_task_id), # TODO: Musisz dodać tę funkcję w d4seo_client.py
            d4seo_client.get_onpage_non_indexable(onpage_task_id), # TODO: Musisz dodać tę funkcję
            d4seo_client.get_security_headers(job_data.domain)
        )
    except Exception as e:
        print(f"Błąd podczas pobierania danych szczegółowych: {e}")
        raise

    # Krok 2: Zbuduj finalny JSON (mapowanie)
    # To jest miejsce na Twoją logikę biznesową.
    # Poniżej znajduje się tylko prosty przykład mapowania kilku pól.
    
    page_metrics = onpage_summary.get("page_metrics", {})
    checks = page_metrics.get("checks", {})

    final_report = {
        "auditMetadata": {
            "domain": job_data.domain,
            "crawlTimestamp": onpage_summary.get("domain_info", {}).get("crawl_end"),
            "totalUrlsCrawled": onpage_summary.get("total_pages"),
            "cms": onpage_summary.get("domain_info", {}).get("cms")
        },
        "metaData": {
            "status": "do_poprawy", # TODO: Dodaj logikę (np. if checks.get('no_description', 0) > 0)
            "summary": f"Wykryto {checks.get('no_description', 0)} stron bez meta opisu.",
            "findings": {
                "longTitles": checks.get("title_too_long", 0),
                "shortTitles": checks.get("title_too_short", 0),
                "missingDescriptions": checks.get("no_description", 0),
                "duplicateDescriptions": page_metrics.get("duplicate_description", 0)
            },
            "examples": [
                {"url": item["url"], "issue": "Zduplikowany Tytuł"} 
                for item in duplicate_tags_data.get("items", [])[:2] # Weź 2 przykłady
            ]
        },
        "performance": {
            "status": "do_poprawy",
            "summary": "Wydajność mobilna wymaga poprawy.",
            "findings": {
                "lcp": lighthouse_data.get("items", [{}])[0].get("lcp", {}).get("displayValue", "N/A"),
                "cls": lighthouse_data.get("items", [{}])[0].get("cls", {}).get("displayValue", "N/A"),
                "mainThreadBlocked": "N/A", # TODO: Znajdź odpowiednie pole
                "unusedJsKiB": 0,
                "largeImageKiB": 0
            },
            "examples": [
                {"url": item["url"], "issue": f"Zasób blokujący renderowanie: {item['initiator']}"}
                for item in lighthouse_data.get("items", [{}])[0].get("render_blocking_resources", {}).get("items", [])[:2]
            ]
        },
        "security": {
            "status": "do_poprawy" if not security_data["hsts"] else "poprawny",
            "summary": "Brak kluczowych nagłówków bezpieczeństwa.",
            "findings": security_data,
            "examples": [
                {"url": f"https://{job_data.domain}", "issue": "Brak nagłówka Strict-Transport-Security (HSTS)"}
            ] if not security_data["hsts"] else []
        }
        # TODO: Zmapuj pozostałe 9 sekcji (headings, content, indexing, etc.)
        # używając danych z onpage_summary, pages_data, links_data itd.
    }
    
    return final_report
