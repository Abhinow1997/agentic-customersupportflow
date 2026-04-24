"""Dependency-free product scraping helper for the Instagram workflow.

The CrewAI flow loads this module dynamically when it wants to enrich a
marketing campaign with product-page context. It is intentionally lightweight
so the demo still works even when third-party scraping libraries are absent.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import re


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self._capture_title = False
        self._capture_h1 = False
        self.meta_description = ""

    def handle_starttag(self, tag: str, attrs):
        attr_map = {k.lower(): v for k, v in attrs}
        if tag.lower() == "title":
            self._capture_title = True
        elif tag.lower() == "h1":
            self._capture_h1 = True
        elif tag.lower() == "meta":
            name = (attr_map.get("name") or attr_map.get("property") or "").lower()
            if name in {"description", "og:description"} and not self.meta_description:
                self.meta_description = attr_map.get("content", "").strip()

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._capture_title = False
        elif tag.lower() == "h1":
            self._capture_h1 = False

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self.title_parts.append(data)
        if self._capture_h1:
            self.h1_parts.append(data)


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def scrape_walmart_product(product_url: str) -> dict[str, Any]:
    """Return a compact metadata payload for a Walmart product page."""
    parsed = urlparse(product_url)
    payload: dict[str, Any] = {
        "product_url": product_url,
        "domain": parsed.netloc,
        "page_title": "",
        "meta_description": "",
        "h1": "",
        "summary": "",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "notes": [],
    }

    if not product_url:
        payload["notes"].append("No product URL supplied.")
        return payload

    try:
        request = Request(
            product_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        with urlopen(request, timeout=10) as response:
            html = response.read(200_000).decode("utf-8", errors="replace")
            payload["content_type"] = response.headers.get("Content-Type", "")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        payload["notes"].append(f"Fetch failed: {exc}")
        return payload

    parser = _MetadataParser()
    try:
        parser.feed(html)
    except Exception as exc:
        payload["notes"].append(f"HTML parse failed: {exc}")

    page_title = _clean("".join(parser.title_parts))
    h1 = _clean("".join(parser.h1_parts))
    meta_description = _clean(parser.meta_description)

    payload["page_title"] = page_title
    payload["meta_description"] = meta_description
    payload["h1"] = h1
    payload["summary"] = " ".join(part for part in [page_title, h1, meta_description] if part)
    if not payload["summary"]:
        payload["notes"].append("No obvious product metadata found in HTML.")
    return payload
