from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .config import AppConfig, load_config
from .gmail_client import GmailClient, GmailMessageSummary
from .rules import RulesEngine
from .search import SearchFilters, build_gmail_query, search_messages

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    items: list[GmailMessageSummary]
    next_page_token: Optional[str]


class Manager:
    """
    The Manager class orchestrates the application logic.
    It decouples the CLI/Automation entry points from the underlying
    Gmail API and Rule logic.
    """

    def __init__(
        self,
        client: Optional[GmailClient] = None,
        config: Optional[AppConfig] = None,
    ) -> None:
        self._client = client or GmailClient.from_oauth()
        self._config = config or load_config()
        self._rules_engine = RulesEngine(self._config.print_rules)

    def search(
        self,
        filters: SearchFilters,
        max_results: int = 20,
        page_token: Optional[str] = None,
    ) -> SearchResult:
        """
        Perform a search using high-level filters.
        """
        items, next_token = search_messages(
            self._client,
            filters,
            max_results=max_results,
            page_token=page_token,
        )
        return SearchResult(items=items, next_page_token=next_token)

    def get_message(self, message_id: str) -> GmailMessageSummary:
        """
        Fetch a single message summary.
        """
        return self._client.get_message_summary(message_id)

    def mark_as_read(self, message_id: str) -> None:
        """
        Mark a message as read.
        """
        logger.info(f"Marking message {message_id} as read.")
        self._client.mark_read(message_id)

    def archive_message(self, message_id: str) -> None:
        """
        Archive a message (remove from INBOX).
        """
        logger.info(f"Archiving message {message_id}.")
        self._client.modify_labels(message_id, remove=["INBOX"])

    def trash_message(self, message_id: str) -> None:
        """
        Trash a message.
        """
        logger.info(f"Trashing message {message_id}.")
        self._client.modify_labels(message_id, add=["TRASH"])
