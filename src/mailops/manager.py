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

    def execute_action(self, message_id: str, action: str, rule_name: str) -> None:
        """
        Execute an action on a message.
        """
        logger.info(f"Executing action '{action}' for rule '{rule_name}' on message {message_id}")

        if action == "print":
            # Printing requires full body
            from .actions.print_action import print_email, PrintConfig
            
            msg = self._client.get_message_full(message_id)
            pconf = PrintConfig(printer_name=self._config.printer_name)
            try:
                print_email(msg, pconf)
                logger.info("Print job sent successfully.")
            except Exception as e:
                logger.error(f"Failed to print message: {e}")
                
        elif action == "archive":
            self.archive_message(message_id)

        elif action == "delete":
            self.trash_message(message_id)

        elif action == "clickup":
            logger.info("ClickUp integration not yet implemented.")
            # Placeholder for future integration

        else:
            logger.warning(f"Unknown action: {action}")

    def run_daily_automation(self, dry_run: bool = False) -> None:
        """
        Check recent emails against rules and execute actions.
        """
        # 1. Fetch recent messages (last 24h)
        # Using "newer_than:1d" to be safe and cover the "morning" run.
        items, _ = search_messages(self._client, SearchFilters(newer_than_days=1, unread_only=False))
        
        logger.info(f"Checking {len(items)} recent messages against {len(self._config.print_rules)} rules.")

        if not self._config.print_rules:
            logger.info("No rules configured.")
            return

        for item in items:
            # Check rules. Converting summary to a lightweight model for rule matching.
            # Currently rules match on headers, so summary is sufficient for matching.
            # But we need to define how strict we want to be.
            # If the rule needs body, we'd have to fetch full.
            # For now, let's assume headers are enough.
            
            # We need to map item -> EmailMessage (partial) for the predicate
            from .models import EmailMessage, EmailContent
            
            partial_msg = EmailMessage(
                message_id=item.message_id,
                thread_id=item.thread_id,
                from_email=item.from_email,
                to_emails=(),
                subject=item.subject,
                date=item.date,
                snippet=item.snippet,
                labels=frozenset(item.label_ids),
                content=EmailContent(), # Empty content for matching
                has_attachments=False,
                attachment_count=0
            )

            matched_rule = self._rules_engine.first_match(partial_msg)
            if matched_rule:
                logger.info(f"Match: Rule '{matched_rule.name}' matched message {item.message_id}")
                if not dry_run:
                    self.execute_action(item.message_id, matched_rule.action, matched_rule.name)
                else:
                    logger.info(f"Dry run: matched action {matched_rule.action}")
