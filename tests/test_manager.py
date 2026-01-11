from unittest.mock import MagicMock

import pytest

from mailops.manager import Manager, SearchResult
from mailops.search import SearchFilters
from mailops.gmail_client import GmailMessageSummary

def test_manager_initializes_with_defaults(monkeypatch):
    # Mock from_oauth to avoid real auth flow
    mock_client_cls = MagicMock()
    monkeypatch.setattr("mailops.manager.GmailClient", mock_client_cls)
    
    # Mock load_config
    mock_config = MagicMock()
    monkeypatch.setattr("mailops.manager.load_config", lambda: mock_config)

    mgr = Manager()
    assert mgr._client is not None
    assert mgr._config is mock_config

def test_search_delegates_to_client_and_returns_result():
    mock_client = MagicMock()
    mock_client.search_messages.return_value = ([], "next_token")
    
    mgr = Manager(client=mock_client)
    filters = SearchFilters(text="test")
    
    res = mgr.search(filters)
    
    assert isinstance(res, SearchResult)
    assert res.items == []
    assert res.next_page_token == "next_token"
    mock_client.search_messages.assert_called_once()

def test_get_message_delegates_to_client():
    mock_client = MagicMock()
    expected = GmailMessageSummary(
        message_id="123", thread_id="t1", from_email="me", 
        subject="sub", date=None, snippet="snip", label_ids=()
    )
    mock_client.get_message_summary.return_value = expected
    
    mgr = Manager(client=mock_client)
    res = mgr.get_message("123")
    
    assert res == expected
    mock_client.get_message_summary.assert_called_with("123")


def test_execute_action_prints(monkeypatch):
    mock_client = MagicMock()
    mock_print_email = MagicMock()
    # Mocking the module where it is imported inside the method
    # Since it's imported inside execute_action, we need to mock it in sys.modules or patch properly.
    # Simpler: mock the print_email in mailops.actions.print_action and Ensure manager imports it.
    
    # Because of local import in Manager: from .actions.print_action import print_email
    # We must mock mailops.actions.print_action
    
    mock_module = MagicMock()
    mock_module.print_email = mock_print_email
    mock_module.PrintConfig = MagicMock
    # monkeypatch.setattr("mailops.manager.print_email", mock_print_email) <-- REMOVED
    
    # Let's try patching sys.modules to be safe regarding the local import
    import sys
    sys.modules["mailops.actions.print_action"] = mock_module

    mgr = Manager(client=mock_client)
    mgr._config = MagicMock()
    mgr._config.printer_name = "MockPrinter"
    
    mgr.execute_action("123", "print", "RuleName")
    
    mock_client.get_message_full.assert_called_with("123")
    mock_print_email.assert_called_once()


def test_run_daily_automation_matches_rule(monkeypatch):
    mock_client = MagicMock()
    
    # Mock search results
    item = GmailMessageSummary(
        message_id="m1", thread_id="t1", from_email="sender@example.com", 
        subject="Newsletter", date=None, snippet="", label_ids=()
    )
    mock_client.search_messages.return_value = ([item], None)
    
    # Mock config with rules
    mock_rule = MagicMock()
    mock_rule.name = "TestRule"
    mock_rule.action = "archive"
    
    mock_config = MagicMock()
    mock_config.print_rules = [mock_rule]
    
    mgr = Manager(client=mock_client, config=mock_config)
    
    # Mock rules engine to return match
    mgr._rules_engine = MagicMock()
    mgr._rules_engine.first_match.return_value = mock_rule
    
    mgr.run_daily_automation()
    
    # Should have called search
    mock_client.search_messages.assert_called_once()
    
    # Should have checked rules
    mgr._rules_engine.first_match.assert_called_once()
    
    # Action was archive -> remove INBOX
    mock_client.modify_labels.assert_called_with("m1", remove=["INBOX"])
