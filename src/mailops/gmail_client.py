from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# Minimal scopes for: reading messages and modifying labels (mark read / add label).
# We are NOT using full mail access.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _default_secrets_dir() -> Path:
    # Keep secrets out of git. You already ignore secrets/ in .gitignore.
    return Path(os.environ.get("MAILOPS_SECRETS_DIR", "secrets")).expanduser()


def _client_secret_path() -> Path:
    p = os.environ.get("MAILOPS_GMAIL_CLIENT_SECRET")
    if p:
        return Path(p).expanduser()
    return _default_secrets_dir() / "gmail_oauth_client.json"


def _token_path() -> Path:
    p = os.environ.get("MAILOPS_GMAIL_TOKEN_PATH")
    if p:
        return Path(p).expanduser()
    return _default_secrets_dir() / "gmail_token.json"


@dataclass(frozen=True)
class GmailMessageSummary:
    message_id: str
    thread_id: Optional[str]
    from_email: str
    subject: str
    date: Optional[datetime]
    snippet: str
    label_ids: tuple[str, ...]


def _parse_headers(payload: dict[str, Any]) -> dict[str, str]:
    headers = payload.get("headers", []) or []
    out: dict[str, str] = {}
    for h in headers:
        name = (h.get("name") or "").strip()
        value = (h.get("value") or "").strip()
        if name:
            out[name.lower()] = value
    return out


def _parse_rfc2822_date(date_str: str) -> Optional[datetime]:
    # Gmail "Date" header is RFC 2822-ish. We keep parsing simple and safe.
    # For our use-case, date is helpful but not critical.
    try:
        # Example: "Tue, 7 Jan 2026 09:21:00 -0500"
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _extract_email_address(from_header: str) -> str:
    # "Name <addr@domain>" -> addr@domain
    from email.utils import parseaddr

    _, addr = parseaddr(from_header or "")
    return addr or (from_header or "").strip()


class GmailClient:
    def __init__(self, creds: Credentials) -> None:
        self._creds = creds
        # cache service client
        self._svc = build("gmail", "v1", credentials=self._creds)

    @staticmethod
    def from_oauth() -> "GmailClient":
        """
        Loads cached OAuth token if present, otherwise performs interactive login.
        Client secret JSON must be present at secrets/gmail_oauth_client.json (default)
        or at MAILOPS_GMAIL_CLIENT_SECRET.
        """
        secrets_dir = _default_secrets_dir()
        secrets_dir.mkdir(parents=True, exist_ok=True)

        token_path = _token_path()
        client_secret = _client_secret_path()

        creds: Optional[Credentials] = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not client_secret.exists():
                    raise FileNotFoundError(
                        f"Missing Gmail OAuth client secret at: {client_secret}. "
                        "Download OAuth client JSON (Desktop app) from Google Cloud Console "
                        "and place it there (or set MAILOPS_GMAIL_CLIENT_SECRET)."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
                try:
                    # Best UX when localhost callbacks work.
                    creds = flow.run_local_server(port=0, open_browser=True)
                except Exception:
                    # WSL/headless fallback: user opens URL manually and pastes code.
                    creds = flow.run_console()
            token_path.write_text(creds.to_json(), encoding="utf-8")

        return GmailClient(creds)

    def search_messages(
        self,
        query: str,
        max_results: int = 20,
        page_token: Optional[str] = None,
        user_id: str = "me",
    ) -> tuple[list[GmailMessageSummary], Optional[str]]:
        """
        Search messages using Gmail query syntax. Returns message summaries and next_page_token.
        This is the core backend primitive for CLI search/filter and future frontend.
        """
        req = (
            self._svc.users()
            .messages()
            .list(userId=user_id, q=query, maxResults=max_results, pageToken=page_token)
        )
        resp = req.execute()
        msgs = resp.get("messages", []) or []
        next_token = resp.get("nextPageToken")

        out: list[GmailMessageSummary] = []
        for m in msgs:
            mid = m.get("id")
            if not mid:
                continue
            out.append(self.get_message_summary(mid, user_id=user_id))

        return out, next_token

    def get_message_summary(self, message_id: str, user_id: str = "me") -> GmailMessageSummary:
        """
        Fetch metadata for a single message (headers + snippet + labels), no body parts.
        """
        req = (
            self._svc.users()
            .messages()
            .get(
                userId=user_id,
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
        )
        msg = req.execute()

        payload = msg.get("payload", {}) or {}
        headers = _parse_headers(payload)

        from_email = _extract_email_address(headers.get("from", ""))
        subject = headers.get("subject", "") or ""
        date = _parse_rfc2822_date(headers.get("date", "") or "")

        snippet = msg.get("snippet", "") or ""
        label_ids = tuple(msg.get("labelIds", []) or [])
        thread_id = msg.get("threadId")

        return GmailMessageSummary(
            message_id=message_id,
            thread_id=thread_id,
            from_email=from_email,
            subject=subject,
            date=date,
            snippet=snippet,
            label_ids=label_ids,
        )

    def modify_labels(
        self,
        message_id: str,
        add: Optional[list[str]] = None,
        remove: Optional[list[str]] = None,
        user_id: str = "me",
    ) -> None:
        body = {"addLabelIds": add or [], "removeLabelIds": remove or []}
        req = self._svc.users().messages().modify(userId=user_id, id=message_id, body=body)
        req.execute()

    def mark_read(self, message_id: str, user_id: str = "me") -> None:
        self.modify_labels(message_id, remove=["UNREAD"], user_id=user_id)

    def add_label(self, message_id: str, label_id: str, user_id: str = "me") -> None:
        self.modify_labels(message_id, add=[label_id], user_id=user_id)
