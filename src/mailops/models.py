from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class EmailContent:
    text: str = ""
    html: str = "" 

@dataclass(frozen=True)
class EmailMessage:
    message_id: str
    thread_id: Optional[str]
    from_email: str
    to_emails: tuple[str, ...]
    subject: str
    date: Optional[datetime]
    snippet: str

    labels: frozenset[str]

    content: EmailContent

    has_attachments: bool
    attachment_count: int

