from __future__ import annotations

import base64

from mailops.gmail.fetch_wsj_link import extract_best_wsj_link


def _b64url(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("utf-8")


def test_extract_best_wsj_link_prefers_wsj_over_unsubscribe() -> None:
    wsj_url = "https://www.wsj.com/edition/print/2026-01-23"
    unsub = "https://www.wsj.com/unsubscribe?x=1"

    html = f"""
    <html>
      <body>
        <a href="{unsub}">unsubscribe</a>
        <a href="{wsj_url}">today's edition</a>
      </body>
    </html>
    """

    msg = {
        "id": "msg1",
        "payload": {
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {"data": _b64url(html)},
                }
            ],
        },
    }

    got = extract_best_wsj_link(msg)
    assert got == wsj_url


def test_extract_best_wsj_link_falls_back_to_text_plain() -> None:
    wsj_url = "https://www.wsj.com/edition/print/2026-01-23"
    text = f"Hello. Link: {wsj_url}\nThanks"

    msg = {
        "id": "msg2",
        "payload": {
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": _b64url(text)},
                }
            ],
        },
    }

    got = extract_best_wsj_link(msg)
    assert got == wsj_url


def test_extract_best_wsj_link_handles_nested_parts() -> None:
    wsj_url = "https://www.wsj.com/edition/print/2026-01-23"
    html = f'<a href="{wsj_url}">WSJ</a>'

    msg = {
        "id": "msg3",
        "payload": {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {
                            "mimeType": "text/html",
                            "body": {"data": _b64url(html)},
                        }
                    ],
                }
            ],
        },
    }

    got = extract_best_wsj_link(msg)
    assert got == wsj_url
