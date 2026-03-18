"""
TruthLens AI – Article Scraper
Extracts clean article text from a URL using newspaper3k or BeautifulSoup fallback.
"""

from __future__ import annotations

import logging
import re
import urllib.request

logger = logging.getLogger("truthlens.scraper")

MAX_CHARS = 10_000


def scrape_article(url: str) -> str | None:
    """
    Attempt to scrape article text from *url*.
    Returns cleaned text or None if scraping fails.
    """
    # ── Try newspaper3k first (best quality) ─────────────────────
    try:
        from newspaper import Article  # type: ignore

        article = Article(url)
        article.download()
        article.parse()
        text = article.text.strip()
        if len(text) > 100:
            logger.info("newspaper3k scraped %d chars from %s", len(text), url)
            return text[:MAX_CHARS]
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("newspaper3k failed: %s", exc)

    # ── Fallback: raw HTML + regex cleaner ───────────────────────
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; TruthLensAI/1.0; "
                    "+https://truthlens.ai/bot)"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        text = _html_to_text(html)
        if len(text) > 100:
            logger.info("Fallback scraper got %d chars from %s", len(text), url)
            return text[:MAX_CHARS]
    except Exception as exc:
        logger.warning("Fallback scraper failed for %s: %s", url, exc)

    return None


def _html_to_text(html: str) -> str:
    """Very simple HTML → plain text conversion (no external deps)."""
    # Remove scripts, styles, head
    html = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Normalise whitespace
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text
