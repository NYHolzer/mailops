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
    # Mock config with real rules to pass __init__ logic
    from mailops.config import PrintRule, MatchCriteria
    
    real_rule = PrintRule(
        name="TestRule", 
        action="archive", 
        match=MatchCriteria(from_exact="sender@example.com")
    )
    
    # We still mock the Rule object that RulesEngine returns if we mock the engine,
    # but Manager.__init__ needs valid config to build the engine first.
    
    mock_config = MagicMock()
    mock_config.print_rules = [real_rule]
    
    mgr = Manager(client=mock_client, config=mock_config)
    
    # Mock rules engine to return match
    mock_rule_result = MagicMock()
    mock_rule_result.name = "TestRule"
    mock_rule_result.action = "archive"
    
    mgr._rules_engine = MagicMock()
    mgr._rules_engine.first_match.return_value = mock_rule_result
    
    mgr.run_daily_automation()
    
    # Should have called search
    mock_client.search_messages.assert_called_once()
    
    # Should have checked rules
    mgr._rules_engine.first_match.assert_called_once()
    
    # Action was archive -> remove INBOX
    mock_client.modify_labels.assert_called_with("m1", remove=["INBOX"])

def test_preview_rule(monkeypatch):
    mock_client = MagicMock()
    
    # Mock search_messages
    mock_search_messages = MagicMock()
    monkeypatch.setattr("mailops.manager.search_messages", mock_search_messages)

    # Mock config with no rules initially, as preview_rule takes a rule directly
    mock_config = MagicMock()
    mock_config.print_rules = [] # Ensure it's an empty list or similar
    
    mgr = Manager(client=mock_client, config=mock_config)

    # Setup: 2 messages, one matches the rule, one does not.
    msg_match = MagicMock(spec=GmailMessageSummary)
    msg_match.message_id = "1"
    msg_match.thread_id = "t1"
    msg_match.subject = "Match Me"
    msg_match.from_email = "sender@example.com"
    msg_match.date = "2022-01-01"
    msg_match.snippet = "snippet"
    msg_match.label_ids = []

    msg_no_match = MagicMock(spec=GmailMessageSummary)
    msg_no_match.message_id = "2"
    msg_no_match.thread_id = "t2"
    msg_no_match.subject = "Ignore Me"
    msg_no_match.from_email = "other@example.com"
    msg_no_match.date = "2022-01-01"
    msg_no_match.snippet = "snippet"
    msg_no_match.label_ids = []
    
    mock_search_messages.return_value = ([msg_match, msg_no_match], None)
    
    # Define a rule that matches "Match Me"
    from mailops.config import PrintRule, MatchCriteria
    rule_config = PrintRule(
        name="Test", 
        match=MatchCriteria(subject_contains="Match"), 
        action="print"
    )
    
    # Call preview_rule
    # Note: preview_rule uses rule_from_config -> real Rule object -> real predicate
    # It does NOT use the mocked _rules_engine which is initialized in __init__
    # This is fine, we want to test the logic of preview_rule using the passed config.
    
    matches = mgr.preview_rule(rule_config, lookback_days=7)
    
    assert len(matches) == 1
    assert matches[0].message_id == "1"
    assert matches[0].subject == "Match Me"
