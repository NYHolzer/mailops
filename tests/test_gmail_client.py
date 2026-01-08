from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Optional

import pytest

import mailops.gmail_client as gc


class _Req:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def execute(self) -> dict[str, Any]:
        return self._payload


class _MessagesAPI:
    def __init__(self, list_payload: dict[str, Any], get_payload_by_id: dict[str, dict[str, Any]]):
        self._list_payload = list_payload
        self._get_payload_by_id = get_payload_by_id

    def list(self, userId: str, q: str, maxResults: int, pageToken: Optional[str] = None):
        # We don't assert q/maxResults here; we just verify the call path works.
        return _Req(self._list_payload)

    def get(self, userId: str, id: str, format: str, metadataHeaders: list[str]):
        if id not in self._get_payload_by_id:
            raise KeyError(f"Missing fixture for id={id}")
        return _Req(self._get_payload_by_id[id])

    def modify(self, userId: str, id: str, body: dict[str, Any]):
        # return an empty response payload
        return _Req({})


class _UsersAPI:
    def __init__(self, messages_api: _MessagesAPI):
        self._messages_api = messages_api

    def messages(self) -> _MessagesAPI:
        return self._messages_api


class _Service:
    def __init__(self, users_api: _UsersAPI):
        self._users_api = users_api

    def users(self) -> _UsersAPI:
        return self._users_api


def _build_fake_client(monkeypatch: pytest.MonkeyPatch) -> gc.GmailClient:
    # Patch googleapiclient.discovery.build() to return our fake service.
    list_payload = {
        "messages": [{"id": "m1"}, {"id": "m2"}],
        "nextPageToken": "NEXT",
    }
    get_payload_by_id = {
        "m1": {
            "id": "m1",
            "threadId": "t1",
            "snippet": "hello world",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "Sender One <one@example.com>"},
                    {"name": "Subject", "value": "Newsletter A"},
                    {"name": "Date", "value": "Tue, 7 Jan 2026 09:21:00 -0500"},
                ]
            },
        },
        "m2": {
            "id": "m2",
            "threadId": None,
            "snippet": "another",
            "labelIds": ["INBOX"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "two@example.com"},
                    {"name": "Subject", "value": "Newsletter B"},
                    {"name": "Date", "value": ""},
                ]
            },
        },
    }

    svc = _Service(_UsersAPI(_MessagesAPI(list_payload, get_payload_by_id)))

    def fake_build(api: str, version: str, credentials):
        assert api == "gmail"
        assert version == "v1"
        return svc

    monkeypatch.setattr(gc, "build", fake_build)

    # We don't need real Credentials here; GmailClient only stores it.
    fake_creds = SimpleNamespace(valid=True)
    return gc.GmailClient(fake_creds)  # type: ignore[arg-type]


def test_get_message_summary_parses_headers(monkeypatch: pytest.MonkeyPatch):
    client = _build_fake_client(monkeypatch)

    s = client.get_message_summary("m1")
    assert s.message_id == "m1"
    assert s.thread_id == "t1"
    assert s.from_email == "one@example.com"
    assert s.subject == "Newsletter A"
    assert isinstance(s.date, datetime)
    assert s.snippet == "hello world"
    assert "INBOX" in s.label_ids


def test_search_messages_returns_summaries_and_next_token(monkeypatch: pytest.MonkeyPatch):
    client = _build_fake_client(monkeypatch)

    items, next_token = client.search_messages("in:inbox newer_than:7d", max_results=2)
    assert next_token == "NEXT"
    assert len(items) == 2
    assert items[0].message_id == "m1"
    assert items[1].message_id == "m2"


def test_mark_read_calls_modify(monkeypatch: pytest.MonkeyPatch):
    client = _build_fake_client(monkeypatch)

    # This just verifies the method path does not error with our fake service.
    client.mark_read("m1")
