from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Iterator, Optional


_URL_RE = re.compile(r"https?://[^\s<>\"]+")


# Domains/patterns commonly present in “click-tracking” style email links
# (Keep this permissive; we only use it for scoring.)
_WSJ_HINTS = (
    "wsj.com",
    "www.wsj.com",
    "wsj.email",
    "dowjones.com",
    "dj.com",
    "links.wsj.com",
    "click.email.wsj.com",
)


def _b64url_decode(data: str) -> bytes:
    """
    Gmail message bodies are base64url encoded.
    """
    if not data:
        return b""
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def _walk_parts(payload: dict) -> Iterator[dict]:
    """
    Walk the Gmail payload tree (multipart messages may be nested).
    Yields each part dict.
    """
    stack = [payload]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        yield node
        parts = node.get("parts") or []
        for child in parts:
            stack.append(child)


def _extract_text_bodies(message_full: dict) -> tuple[list[str], list[str]]:
    """
    Return (html_bodies, text_bodies) decoded from the message payload.
    """
    payload = message_full.get("payload") or {}
    html: list[str] = []
    text: list[str] = []

    for part in _walk_parts(payload):
        mime = (part.get("mimeType") or "").lower().strip()
        body = part.get("body") or {}
        data = body.get("data")  # inline body (not attachments)
        if not data:
            continue

        raw = _b64url_decode(data)
        try:
            s = raw.decode("utf-8", errors="replace")
        except Exception:
            continue

        if mime == "text/html":
            html.append(s)
        elif mime == "text/plain":
            text.append(s)

    return html, text


def _score_url(url: str) -> int:
    """
    Heuristic scoring: higher is “more likely the WSJ edition/download link”.
    We keep it simple and adjustable.
    """
    u = url.lower()
    score = 0

    # Strong signal: actual wsj domain present
    if "wsj.com" in u:
        score += 50

    # Common “edition/print” signals
    if "/edition" in u:
        score += 25
    if "/print" in u or "print" in u:
        score += 10

    # Click-tracking-ish hints
    if any(h in u for h in _WSJ_HINTS):
        score += 10

    # Prefer https over http
    if u.startswith("https://"):
        score += 2

    # Avoid obvious unsubscribe / preferences / privacy
    if "unsubscribe" in u or "preferences" in u or "privacy" in u:
        score -= 40

    return score


def extract_best_wsj_link(message_full: dict) -> Optional[str]:
    """
    Given a Gmail message fetched with format='full', extract the most likely WSJ link
    (often a tracking link) suitable for feeding into wsj.download.download_from_email_link().

    Returns None if no URLs found.
    """
    html_bodies, text_bodies = _extract_text_bodies(message_full)

    # Prefer HTML for richer link presence; fallback to text/plain
    candidates: list[str] = []
    for blob in html_bodies + text_bodies:
        candidates.extend(_URL_RE.findall(blob))

    if not candidates:
        return None

    # De-dup while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        uniq.append(c)

    # Pick the highest scoring candidate
    best = max(uniq, key=_score_url)
    return best
