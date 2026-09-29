"""
Web search utility supporting DDGS and Wikipedia search fallbacks (100% free, no API keys needed).
"""

import time
import requests
from typing import List, Dict, Any

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


def search_ddg(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search DuckDuckGo using ddgs package."""
    if not query or not query.strip() or DDGS is None:
        return []

    results = []
    clean_query = query.strip()

    try:
        ddgs = DDGS()
        raw_results = list(ddgs.text(clean_query, max_results=max_results))
        for item in raw_results:
            title = item.get("title", "").strip()
            href = item.get("href", "").strip()
            body = item.get("body", "").strip()
            if href and (title or body):
                results.append({
                    "title": title or href,
                    "href": href,
                    "body": body
                })
    except Exception as e:
        # Retry with simpler query
        try:
            time.sleep(0.5)
            ddgs = DDGS()
            raw_results = list(ddgs.text(clean_query, max_results=max_results))
            for item in raw_results:
                title = item.get("title", "").strip()
                href = item.get("href", "").strip()
                body = item.get("body", "").strip()
                if href and (title or body):
                    results.append({
                        "title": title or href,
                        "href": href,
                        "body": body
                    })
        except Exception:
            pass

    return results


def search_wikipedia(query: str, max_results: int = 2) -> List[Dict[str, str]]:
    """Search Wikipedia as an authoritative fallback for topics."""
    headers = {"User-Agent": "ResearchAgent/1.0 (Educational research agent)"}
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "opensearch",
        "search": query,
        "limit": max_results,
        "namespace": 0,
        "format": "json"
    }
    results = []
    try:
        r = requests.get(url, params=params, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            titles = data[1] if len(data) > 1 else []
            snippets = data[2] if len(data) > 2 else []
            links = data[3] if len(data) > 3 else []
            for t, s, l in zip(titles, snippets, links):
                results.append({
                    "title": f"{t} - Wikipedia",
                    "href": l,
                    "body": s or f"Wikipedia article for {t}"
                })
    except Exception:
        pass
    return results


def search_web(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search the web for query, trying DDGS first with Wikipedia fallback.
    """
    results = search_ddg(query, max_results=max_results)
    if len(results) < 2:
        wiki_results = search_wikipedia(query, max_results=2)
        seen = {r["href"] for r in results}
        for wr in wiki_results:
            if wr["href"] not in seen:
                results.append(wr)
    return results


def multi_query_search(queries: List[str], max_results_per_query: int = 4) -> List[Dict[str, str]]:
    """
    Execute multiple search queries and combine deduplicated results by URL.
    """
    seen_urls = set()
    combined_results = []

    for q in queries:
        query_results = search_web(q, max_results=max_results_per_query)
        for res in query_results:
            url = res["href"]
            if url not in seen_urls:
                seen_urls.add(url)
                combined_results.append(res)
        time.sleep(0.3)

    return combined_results
