# app/rag/scraper.py
"""
Walmart policy scraper using Scrapling.

Fetcher tiers:
  - Fetcher.get()            -> corporate.walmart.com, marketplacelearn (static)
  - StealthyFetcher.fetch()  -> walmart.com/help (React / JS-rendered)
  - Fetcher.get() + PyPDF2   -> PDF documents

Usage (standalone):
    cd backend
    python -m app.rag.scraper                    # scrape all
    python -m app.rag.scraper --domain returns   # scrape one domain
    python -m app.rag.scraper --list             # list sources
    python -m app.rag.scraper --stats            # show ChromaDB stats
"""
from __future__ import annotations

import os
import re
import time
import logging
import tempfile
import argparse
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("rag.scraper")

# ── Scrapling imports ─────────────────────────────────────────────────────
# Base Fetcher (HTTP only, no browser) is always available after `pip install scrapling`
# StealthyFetcher needs browser binaries: `scrapling install` or `pip install scrapling[all]`
HAS_SCRAPLING = False
HAS_STEALTHY = False
try:
    from scrapling.fetchers import Fetcher
    HAS_SCRAPLING = True
    try:
        from scrapling.fetchers import StealthyFetcher
        HAS_STEALTHY = True
    except Exception:
        logger.info("StealthyFetcher not available -- run 'scrapling install' for JS page support")
except ImportError:
    logger.warning("scrapling not installed -- scraper will not work")

try:
    from PyPDF2 import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

from app.rag.chunker import chunk_policy_text
from app.rag.store import get_store

# ── Config ────────────────────────────────────────────────────────────────
REQUEST_DELAY = 2.0   # seconds between requests (respectful scraping)


# ── Policy Source Registry ────────────────────────────────────────────────

@dataclass
class PolicySource:
    url: str
    domain: str
    policy_name: str
    priority: str                         # CRITICAL | HIGH | MEDIUM | LOW
    content_type: str = "html"            # html | pdf
    needs_js: bool = False                # True -> StealthyFetcher
    css_selectors: list = field(default_factory=list)


POLICY_SOURCES: list[PolicySource] = [
    # ── RETURNS & REFUNDS ────────────────────────────────────────────
    PolicySource(
        url="https://www.walmart.com/help/article/walmart-standard-return-policy/adc0dfb692954e67a4de206fb8d9e03a",
        domain="returns", policy_name="Standard Return Policy (90-day)", priority="CRITICAL",
        needs_js=True, css_selectors=["article", "main", "[data-testid='article-content']"],
    ),
    PolicySource(
        url="https://www.walmart.com/help/article/walmart-marketplace-return-policy/63c3566a9d3546858582acae2fbfdb7e",
        domain="returns", policy_name="Marketplace Return Policy (30-day)", priority="CRITICAL",
        needs_js=True, css_selectors=["article", "main"],
    ),
    PolicySource(
        url="https://www.walmart.com/cp/returns/1231920",
        domain="returns", policy_name="Free Returns & Non-Returnable Items", priority="CRITICAL",
        needs_js=True, css_selectors=["main", ".category-page"],
    ),
    PolicySource(
        url="https://www.walmart.com/help/article/refunds/a86a0400e237444cb9a5f3c3ce500d1b",
        domain="returns", policy_name="Refund Processing & Timelines", priority="HIGH",
        needs_js=True, css_selectors=["article", "main"],
    ),
    PolicySource(
        url="https://marketplacelearn.walmart.com/guides/Order%20management/Returns%20&%20refunds/returns-policy",
        domain="returns", policy_name="Seller-Fulfilled Returns Policy", priority="MEDIUM",
        css_selectors=["article", ".guide-content", "main", ".markdown-body"],
    ),

    # ── PRICE MATCH ──────────────────────────────────────────────────
    PolicySource(
        url="https://www.walmart.com/help/article/walmart-price-match-policy/6295d9e1a501489b9aa40a60c899b288",
        domain="pricing", policy_name="Price Match Policy", priority="HIGH",
        needs_js=True, css_selectors=["article", "main"],
    ),
    PolicySource(
        url="https://corporate.walmart.com/askwalmart/does-walmart-price-match",
        domain="pricing", policy_name="Corporate Price Match FAQ", priority="HIGH",
        css_selectors=["article", "main", ".content-area"],
    ),

    # ── COUPON POLICY ────────────────────────────────────────────────
    PolicySource(
        url="https://corporate.walmart.com/policies",
        domain="coupons", policy_name="Coupon Policy (OP-41) & Corporate Policies", priority="HIGH",
        css_selectors=["article", "main", ".content-area"],
    ),

    # ── WALMART+ ─────────────────────────────────────────────────────
    PolicySource(
        url="https://www.walmart.com/help/article/walmart-terms-of-use/de696dfa1dd4423bb1005668dd19b845",
        domain="walmart_plus", policy_name="Walmart+ Terms of Use", priority="CRITICAL",
        needs_js=True, css_selectors=["article", "main"],
    ),
    PolicySource(
        url="https://www.walmart.com/plus",
        domain="walmart_plus", policy_name="Walmart+ Benefits Overview", priority="CRITICAL",
        needs_js=True, css_selectors=["main"],
    ),
    PolicySource(
        url="https://www.walmart.com/plus/frequently-asked-questions",
        domain="walmart_plus", policy_name="Walmart+ FAQ", priority="HIGH",
        needs_js=True, css_selectors=["main", ".faq-content"],
    ),

    # ── SHIPPING ─────────────────────────────────────────────────────
    PolicySource(
        url="https://www.walmart.com/help/article/walmart-benefits-free-shipping-and-free-delivery-from-your-store/d1738a201207485c99fd53ccdbc49699",
        domain="shipping", policy_name="Shipping & Delivery Benefits", priority="HIGH",
        needs_js=True, css_selectors=["article", "main"],
    ),
    PolicySource(
        url="https://marketplacelearn.walmart.com/guides/Policies%20&%20standards/Shipping%20&%20fulfillment/Shipping-and-fulfillment-policy",
        domain="shipping", policy_name="Marketplace Shipping Policy", priority="MEDIUM",
        css_selectors=["article", ".guide-content", "main"],
    ),

    # ── WARRANTY ─────────────────────────────────────────────────────
    PolicySource(
        url="https://www.walmart.com/help/article/walmart-protection-plans-by-allstate/87e60d4d34b340e0adfe815afe402d19",
        domain="warranty", policy_name="Protection Plans by Allstate", priority="HIGH",
        needs_js=True, css_selectors=["article", "main"],
    ),

    # ── PRIVACY ──────────────────────────────────────────────────────
    PolicySource(
        url="https://corporate.walmart.com/privacy-security/walmart-privacy-notice",
        domain="privacy", policy_name="Customer Privacy Notice", priority="MEDIUM",
        css_selectors=["article", "main", ".content-area"],
    ),

    # ── PRODUCT SAFETY ───────────────────────────────────────────────
    PolicySource(
        url="https://corporate.walmart.com/content/dam/corporate/documents/suppliers/requirements/compliance-areas/u-s-product-quality-and-compliance-manual.pdf",
        domain="product_safety", policy_name="US Product Quality & Compliance Manual", priority="MEDIUM",
        content_type="pdf",
    ),
    PolicySource(
        url="https://corporate.walmart.com/suppliers/requirements/compliance-areas",
        domain="product_safety", policy_name="Supplier Compliance Areas", priority="LOW",
        css_selectors=["article", "main", ".content-area"],
    ),

    # ── PHARMACY ─────────────────────────────────────────────────────
    PolicySource(
        url="https://www.walmart.com/cp/4-prescriptions/1078664",
        domain="pharmacy", policy_name="$4 Generic Prescription Program", priority="MEDIUM",
        needs_js=True, css_selectors=["main"],
    ),

    # ── LEGAL ────────────────────────────────────────────────────────
    PolicySource(
        url="https://www.walmart.com/help/article/walmart-com-terms-of-use/3b75080af40340d6bbd596f116fae5a0",
        domain="legal", policy_name="Walmart.com Terms of Use", priority="MEDIUM",
        needs_js=True, css_selectors=["article", "main"],
    ),
    PolicySource(
        url="https://business.walmart.com/help/article/gift-card-terms-and-conditions/e949c6cb64354a779868406c7b5033d8",
        domain="legal", policy_name="Gift Card Terms & Conditions", priority="MEDIUM",
        needs_js=True, css_selectors=["article", "main"],
    ),

    # ── ACCESSIBILITY ────────────────────────────────────────────────
    PolicySource(
        url="https://www.walmart.com/help/article/responsible-disclosure-and-accessibility-policies/0f173dab8bd942da84b1cd7ab5ffc3cb",
        domain="accessibility", policy_name="Accessibility & Disclosure", priority="MEDIUM",
        needs_js=True, css_selectors=["article", "main"],
    ),

    # ── GENERAL ──────────────────────────────────────────────────────
    PolicySource(
        url="https://corporate.walmart.com/askwalmart",
        domain="general", policy_name="Ask Walmart (FAQ Hub)", priority="REFERENCE",
        css_selectors=["article", "main", ".content-area"],
    ),
]


# ── Scraper ───────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Normalize whitespace and strip noise."""
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def _extract_content(page, source: PolicySource) -> Optional[str]:
    """Try CSS selectors in order, return first with substantial content."""
    for selector in source.css_selectors:
        try:
            element = page.css_first(selector)
            if element:
                text = element.get_all_text(strip=True)
                if text and len(text) > 200:
                    return _clean_text(text)
        except Exception:
            continue

    # Fallback: all page text
    try:
        text = page.get_all_text(strip=True)
        if text and len(text) > 200:
            return _clean_text(text)
    except Exception:
        pass
    return None


def _fetch_html(source: PolicySource) -> Optional[str]:
    """Fetch an HTML page using the appropriate Scrapling fetcher."""
    if not HAS_SCRAPLING:
        raise RuntimeError("scrapling is not installed")

    # Strategy: Use StealthyFetcher for JS pages if available,
    # otherwise always fall back to plain Fetcher (gets partial content
    # from SSR/initial HTML -- typically 40-70% of full page).
    use_stealthy = source.needs_js and HAS_STEALTHY

    try:
        if use_stealthy:
            page = StealthyFetcher.fetch(
                source.url,
                headless=True,
                network_idle=True,
                timeout=30000,
                disable_resources=True,
            )
        else:
            if source.needs_js and not HAS_STEALTHY:
                logger.info("  StealthyFetcher not available, using plain Fetcher (partial content)")
            page = Fetcher.get(
                source.url,
                stealthy_headers=True,
                timeout=30,
            )

        if page.status != 200:
            logger.warning("  HTTP %d for %s", page.status, source.url)
            return None

        return _extract_content(page, source)

    except Exception as exc:
        logger.warning("  Primary fetch failed: %s", exc)
        # Fallback: try plain Fetcher even if Stealthy was used
        if use_stealthy:
            try:
                logger.info("  Retrying with plain Fetcher...")
                page = Fetcher.get(source.url, stealthy_headers=True, timeout=30)
                if page.status == 200:
                    return _extract_content(page, source)
            except Exception as exc2:
                logger.error("  Fallback also failed: %s", exc2)
        return None


def _fetch_pdf(source: PolicySource) -> Optional[str]:
    """Download PDF via Fetcher and extract text."""
    if not HAS_PYPDF:
        logger.warning("  PyPDF2 not installed -- skipping PDF")
        return None
    if not HAS_SCRAPLING:
        raise RuntimeError("scrapling is not installed")

    try:
        page = Fetcher.get(source.url, timeout=30)
        if page.status != 200:
            return None

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(page.body)
            tmp_path = tmp.name

        reader = PdfReader(tmp_path)
        parts = [pg.extract_text() for pg in reader.pages if pg.extract_text()]
        os.unlink(tmp_path)
        return _clean_text("\n\n".join(parts))
    except Exception as exc:
        logger.error("  PDF extraction failed: %s", exc)
        return None


def scrape_source(source: PolicySource) -> Optional[str]:
    """Scrape a single policy source. Returns cleaned text or None."""
    if source.content_type == "pdf":
        return _fetch_pdf(source)
    return _fetch_html(source)


# ── Pipeline orchestrator ─────────────────────────────────────────────────

def run_scrape_pipeline(
    domain_filter: str | None = None,
    delay: float = REQUEST_DELAY,
) -> dict:
    """
    Full scrape -> chunk -> store pipeline.

    Returns a stats dict:
      { attempted, success, failed, total_chunks, total_tokens }
    """
    store = get_store()
    sources = POLICY_SOURCES
    if domain_filter:
        sources = [s for s in sources if s.domain == domain_filter]

    stats = {"attempted": 0, "success": 0, "failed": 0,
             "total_chunks": 0, "total_tokens": 0}

    logger.info("Starting scrape pipeline: %d sources", len(sources))

    for i, source in enumerate(sources, 1):
        stats["attempted"] += 1
        logger.info(
            "[%d/%d] %s  (%s)",
            i, len(sources), source.policy_name,
            "StealthyFetcher" if source.needs_js else "Fetcher",
        )

        text = scrape_source(source)
        if not text:
            logger.warning("  FAILED -- no content extracted")
            stats["failed"] += 1
            continue

        logger.info("  Extracted %d chars", len(text))

        chunks = chunk_policy_text(
            text,
            source_url=source.url,
            domain=source.domain,
            policy_name=source.policy_name,
            priority=source.priority,
        )
        chunk_tokens = sum(c["token_count"] for c in chunks)
        logger.info("  Chunked -> %d chunks (%d tokens)", len(chunks), chunk_tokens)

        store.upsert_chunks(chunks)
        stats["success"] += 1
        stats["total_chunks"] += len(chunks)
        stats["total_tokens"] += chunk_tokens

        if i < len(sources):
            time.sleep(delay)

    logger.info(
        "Scrape complete: %d/%d success, %d chunks, %d tokens",
        stats["success"], stats["attempted"],
        stats["total_chunks"], stats["total_tokens"],
    )
    return stats


# ── CLI entrypoint ────────────────────────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Walmart Policy Scraper")
    parser.add_argument("--domain", type=str, default=None,
                        help="Only scrape a specific domain")
    parser.add_argument("--list", action="store_true",
                        help="List all policy sources")
    parser.add_argument("--stats", action="store_true",
                        help="Show ChromaDB collection stats")
    parser.add_argument("--query", "-q", type=str, default=None,
                        help="Test query against ChromaDB")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY,
                        help="Delay between requests (seconds)")
    args = parser.parse_args()

    if args.list:
        print(f"\n{'Domain':<20} {'Priority':<10} {'JS?':<5} {'Name'}")
        print("-" * 85)
        for s in POLICY_SOURCES:
            js = "Yes" if s.needs_js else "No"
            print(f"{s.domain:<20} {s.priority:<10} {js:<5} {s.policy_name}")
        print(f"\nTotal: {len(POLICY_SOURCES)} sources")
        return

    if args.stats:
        store = get_store()
        stats = store.get_stats()
        print(f"\nChromaDB: {stats['total_chunks']} chunks")
        for domain, count in stats.get("domains", {}).items():
            print(f"  {domain:<20} {count} chunks")
        return

    if args.query:
        store = get_store()
        results = store.query_by_text(args.query, n_results=5)
        print(f"\nResults for '{args.query}':\n")
        for r in results:
            m = r["metadata"]
            print(f"  [{r['similarity']:.3f}] {m['domain']}/{m['policy_name']}")
            print(f"         {r['content'][:120]}...\n")
        return

    run_scrape_pipeline(domain_filter=args.domain, delay=args.delay)


if __name__ == "__main__":
    main()
