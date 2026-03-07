# app/rag/chunker.py
"""
Text chunker for RAG pipeline.

Splits scraped policy text into overlapping chunks suitable for
ChromaDB embedding + retrieval. Preserves section headers as metadata.
"""
from __future__ import annotations

import re
import hashlib
from datetime import datetime, timezone

try:
    import tiktoken
    _encoder = tiktoken.get_encoding("cl100k_base")
except ImportError:
    _encoder = None

# Defaults
CHUNK_SIZE = 512      # tokens per chunk
CHUNK_OVERLAP = 64    # overlap between consecutive chunks


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken if available, else approximate."""
    if _encoder:
        return len(_encoder.encode(text))
    return len(text.split()) * 4 // 3


def chunk_policy_text(
    text: str,
    *,
    source_url: str,
    domain: str,
    policy_name: str,
    priority: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict]:
    """
    Split policy text into overlapping chunks with metadata.

    Returns a list of dicts ready for PolicyVectorStore.upsert_chunks().
    """
    sections = _split_sections(text)
    chunks: list[dict] = []
    global_idx = 0

    for header, body in sections:
        sentences = _split_sentences(body)
        current: list[str] = []
        current_tokens = 0

        for sent in sentences:
            sent_tokens = count_tokens(sent)

            if current_tokens + sent_tokens > chunk_size and current:
                chunk_text = " ".join(current)
                chunks.append(_make_chunk(
                    chunk_text, source_url, domain, policy_name,
                    priority, global_idx, header,
                ))
                global_idx += 1

                # Keep tail for overlap
                overlap_sents: list[str] = []
                overlap_tok = 0
                for s in reversed(current):
                    st = count_tokens(s)
                    if overlap_tok + st > overlap:
                        break
                    overlap_sents.insert(0, s)
                    overlap_tok += st
                current = overlap_sents
                current_tokens = overlap_tok

            current.append(sent)
            current_tokens += sent_tokens

        # Flush remainder
        if current:
            chunk_text = " ".join(current)
            if count_tokens(chunk_text) > 30:
                chunks.append(_make_chunk(
                    chunk_text, source_url, domain, policy_name,
                    priority, global_idx, header,
                ))
                global_idx += 1

    # Backfill total_chunks
    for c in chunks:
        c["total_chunks"] = len(chunks)

    return chunks


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_chunk(
    text: str, source_url: str, domain: str, policy_name: str,
    priority: str, idx: int, section: str,
) -> dict:
    content_hash = hashlib.md5(text.encode()).hexdigest()[:12]
    safe_name = re.sub(r"[^a-z0-9]", "_", policy_name.lower())[:40]
    return {
        "chunk_id":       f"{domain}_{safe_name}_{idx:03d}",
        "source_url":     source_url,
        "domain":         domain,
        "policy_name":    policy_name,
        "priority":       priority,
        "chunk_index":    idx,
        "total_chunks":   0,
        "content":        text,
        "token_count":    count_tokens(text),
        "content_hash":   content_hash,
        "section_header": section,
        "scraped_at":     datetime.now(timezone.utc).isoformat(),
    }


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split text at detected header lines."""
    lines = text.split("\n")
    sections: list[tuple[str, str]] = []
    header = "Introduction"
    body_lines: list[str] = []

    for line in lines:
        s = line.strip()
        if (
            s and len(s) < 100
            and (
                s.isupper()
                or re.match(r"^#{1,3}\s", s)
                or re.match(r"^\d+\.\s+[A-Z]", s)
                or re.match(r"^[A-Z][A-Za-z\s&:,\-]{5,60}$", s)
            )
        ):
            if body_lines:
                sections.append((header, "\n".join(body_lines)))
            header = s.lstrip("#").strip()
            body_lines = []
        else:
            body_lines.append(line)

    if body_lines:
        sections.append((header, "\n".join(body_lines)))

    return sections if sections else [("Full Document", text)]


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [s.strip() for s in sentences if s.strip()]
