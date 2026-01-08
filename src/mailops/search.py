from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .gmail_client import GmailClient, GmailMessageSummary


@dataclass(frozen=True)
class SearchFilters:
    """
    High-level, user-facing search filters.
    These map cleanly to Gmail query syntax internally.
    """
    text: Optional[str] = None
    from_addr: Optional[str] = None
    newer_than_days: Optional[int] = None
    unread_only: bool = True
    inbox_only: bool = True


def build_gmail_query(filters: SearchFilters) -> str:
    """
    Convert SearchFilters into a Gmail query string.
    """
    parts: list[str] = []

    if filters.inbox_only:
        parts.append("in:inbox")

    if filters.unread_only:
        parts.append("is:unread")

    if filters.from_addr:
        parts.append(f"from:{filters.from_addr}")

    if filters.newer_than_days is not None:
        parts.append(f"newer_than:{filters.newer_than_days}d")

    if filters.text:
        # Gmail treats bare text as a full-text search
        parts.append(filters.text)

    return " ".join(parts).strip()


def search_messages(
    client: GmailClient,
    filters: SearchFilters,
    *,
    max_results: int = 20,
    page_token: Optional[str] = None,
) -> tuple[list[GmailMessageSummary], Optional[str]]:
    """
    Search messages using user-friendly filters.
    Returns message summaries + next page token.
    """
    query = build_gmail_query(filters)
    return client.search_messages(query, max_results=max_results, page_token=page_token)
