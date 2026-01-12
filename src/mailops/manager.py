from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .config import AppConfig, load_config
from .gmail_client import GmailClient, GmailMessageSummary
from .rules import RulesEngine, rule_from_config
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
        self._rules_engine = RulesEngine(
            rule_from_config(r) for r in self._config.print_rules
        )

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
            from .actions.clickup_action import create_task_from_email, get_clickup_config
            cfg = get_clickup_config()
            if not cfg:
                logger.error("ClickUp configuration missing (env vars). Cannot create task.")
                return

            summary = self._client.get_message_summary(message_id)
            # Create partial EmailMessage for the action
            from .models import EmailMessage, EmailContent
            msg = EmailMessage(
                message_id=summary.message_id,
                thread_id=summary.thread_id,
                from_email=summary.from_email,
                to_emails=(),
                subject=summary.subject,
                date=summary.date,
                snippet=summary.snippet,
                labels=frozenset(summary.label_ids),
                content=EmailContent(),
                has_attachments=False,
                attachment_count=0
            )
            
            try:
                create_task_from_email(msg, cfg)
            except Exception:
                pass # Error logged inside helper

        else:
            logger.warning(f"Unknown action: {action}")

    def get_automation_plan(self, newer_than_days: int = 1) -> list[tuple[GmailMessageSummary, Rule]]:
        """
        Generate a plan of actions by checking recent emails against rules.
        """
        items, _ = search_messages(self._client, SearchFilters(newer_than_days=newer_than_days, unread_only=False))
        
        logger.info(f"Checking {len(items)} recent messages against {len(self._config.print_rules)} rules.")
        if not self._config.print_rules:
            logger.info("No rules configured.")
            return []

        from .models import EmailMessage, EmailContent
        # Import Rule type for return annotation
        from .rules import Rule

        matches = []
        for item in items:
            partial_msg = EmailMessage(
                message_id=item.message_id,
                thread_id=item.thread_id,
                from_email=item.from_email,
                to_emails=(),
                subject=item.subject,
                date=item.date,
                snippet=item.snippet,
                labels=frozenset(item.label_ids),
                content=EmailContent(),
                has_attachments=False,
                attachment_count=0
            )

            matched_rule = self._rules_engine.first_match(partial_msg)
            if matched_rule:
                matches.append((item, matched_rule))
        
        return matches

    def execute_automation_plan(self, plan: list[tuple[GmailMessageSummary, "Rule"]]) -> None: # type: ignore
        """
        Execute the actions in the plan.
        """
        for item, rule in plan:
            logger.info(f"Executing plan: Rule '{rule.name}' matched message {item.message_id}")
            self.execute_action(item.message_id, rule.action, rule.name)

    def run_daily_automation(self, dry_run: bool = False) -> None:
        """
        Check recent emails against rules and execute actions.
        """
        plan = self.get_automation_plan()
        
        for item, rule in plan:
            if not dry_run:
                logger.info(f"Match: Rule '{rule.name}' matched message {item.message_id}")
                self.execute_action(item.message_id, rule.action, rule.name)
            else:
                logger.info(f"Dry run: matched action {rule.action} for rule {rule.name}")

    def preview_rule(self, rule_config: "PrintRule", lookback_days: int = 7) -> list[GmailMessageSummary]:
        """
        Check which emails from the last N days would match a specific rule configuration.
        Used for UI "Test Rule" feature.
        """
        # Fetch broader candidates (unread or read)
        # We search 'newer_than:Nd'
        # We don't filter by sender in the query because the rule might have complex exclusions
        # that Gmail query doesn't handle easily, or we rely on the python predicate for exactness.
        items, _ = search_messages(self._client, SearchFilters(newer_than_days=lookback_days, unread_only=False, inbox_only=False))
        
        # Convert config to matching rule
        rule = rule_from_config(rule_config)
        
        from .models import EmailMessage, EmailContent
        matches = []
        for item in items:
             partial_msg = EmailMessage(
                message_id=item.message_id,
                thread_id=item.thread_id,
                from_email=item.from_email,
                to_emails=(),
                subject=item.subject,
                date=item.date,
                snippet=item.snippet,
                labels=frozenset(item.label_ids),
                content=EmailContent(),
                has_attachments=False,
                attachment_count=0
            )
             if rule.predicate(partial_msg):
                 matches.append(item)
        
        return matches
