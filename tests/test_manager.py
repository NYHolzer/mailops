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
