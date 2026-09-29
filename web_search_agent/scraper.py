"""
Web scraper utility for fetching and extracting readable text from article URLs.
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Optional

# Standard realistic desktop User-Agent to avoid blocking
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean_text(text: str) -> str:
    """Normalize whitespace and remove excessive newlines."""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def scrape_url(url: str, timeout: int = 8, max_chars: int = 3500) -> Optional[str]:
    """
    Fetch a URL and extract its main article / readable text content.
    Returns cleaned text or None if fetching/parsing fails.
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        return None

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        if response.status_code != 200:
            return None

        # Check content type is HTML
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Strip scripts, styles, metadata, forms, navigation, footer, ads
        unwanted_tags = [
            "script", "style", "nav", "footer", "header", "aside",
            "form", "noscript", "svg", "button", "iframe"
        ]
        for tag in soup(unwanted_tags):
            tag.decompose()

        # Prioritize main article tags if present
        main_container = (
            soup.find("article")
            or soup.find("main")
            or soup.find(id=re.compile(r"content|main|article|body", re.I))
            or soup.find(class_=re.compile(r"content|article-body|post-content", re.I))
            or soup.body
        )

        if not main_container:
            return None

        # Collect text from paragraphs and headings
        paragraphs = main_container.find_all(["p", "h1", "h2", "h3", "li"])
        extracted_lines = []
        for p in paragraphs:
            text = p.get_text(separator=" ", strip=True)
            if len(text) > 25:  # Ignore tiny navigation crumbs or author links
                extracted_lines.append(text)

        full_content = "\n\n".join(extracted_lines)
        if not full_content.strip():
            # Fallback to general text extraction
            full_content = main_container.get_text(separator="\n", strip=True)

        cleaned = clean_text(full_content)
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars] + "\n...[truncated]"

        return cleaned if len(cleaned) >= 50 else None

    except Exception:
        # Ignore timeouts, connection errors, ssl errors gracefully
        return None
