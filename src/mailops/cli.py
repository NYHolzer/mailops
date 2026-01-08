from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from typing import Optional

from .gmail_client import GmailClient, GmailMessageSummary
from .search import SearchFilters, build_gmail_query


@dataclass
class _PagerState:
    page_token: Optional[str] = None
    next_page_token: Optional[str] = None


def _print_results(items: list[GmailMessageSummary]) -> None:
    if not items:
        print("\nNo results.\n")
        return

    print("\nResults:\n")
    for i, m in enumerate(items, start=1):
        from_part = m.from_email or "(unknown sender)"
        subj = (m.subject or "").strip() or "(no subject)"
        print(f"{i:>2}. {subj}  |  {from_part}")
    print("")


def _help() -> None:
    print(
        "\nCommands:\n"
        "  /s <text>          set full-text search (subject/from/body)\n"
        "  /from <addr|dom>   filter by sender email or domain\n"
        "  /days <n>          restrict to last n days\n"
        "  /unread on|off     unread only (default on)\n"
        "  /inbox on|off      inbox only (default on)\n"
        "  /show              re-run search and show results\n"
        "  /next              next page\n"
        "  /prev              previous page (limited; see note)\n"
        "  <nums>             select messages by number, e.g. 1,3,5\n"
        "  /q                 quit\n"
        "\nNotes:\n"
        "  Gmail pagination uses page tokens. We support /next.\n"
        "  /prev is best-effort by re-running from the start (v1).\n"
    )


def _parse_int(s: str) -> Optional[int]:
    try:
        return int(s.strip())
    except Exception:
        return None


def _parse_selection(s: str, max_n: int) -> list[int]:
    # "1,3,5" -> [1,3,5] (1-based)
    out: list[int] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        n = _parse_int(part)
        if n is None:
            continue
        if 1 <= n <= max_n:
            out.append(n)
    # de-dupe while preserving order
    seen = set()
    deduped: list[int] = []
    for n in out:
        if n not in seen:
            seen.add(n)
            deduped.append(n)
    return deduped


def configure() -> int:
    """
    Interactive configuration wizard (v1):
      - Search/filter Inbox
      - Let user select example newsletter emails
      - Print selected message IDs (next step will infer rules)
    """
    client = GmailClient.from_oauth()

    filters = SearchFilters(text=None, from_addr=None, newer_than_days=7, unread_only=True, inbox_only=True)
    pager = _PagerState()
    history_tokens: list[Optional[str]] = [None]  # best-effort /prev by replaying pages

    def run_search(page_token: Optional[str]) -> tuple[list[GmailMessageSummary], Optional[str]]:
        q = build_gmail_query(filters)
        print(f"\nQuery: {q}\n")
        items, next_tok = client.search_messages(q, max_results=20, page_token=page_token)
        pager.page_token = page_token
        pager.next_page_token = next_tok
        _print_results(items)
        return items, next_tok

    print("\nMailOps Configure (v1)\n")
    _help()

    items, _ = run_search(None)

    while True:
        raw = input("mailops> ").strip()
        if not raw:
            continue

        if raw in ("/q", "q", "quit", "exit"):
            return 0

        if raw in ("/h", "/help", "help"):
            _help()
            continue

        if raw.startswith("/s "):
            filters = replace(filters, text=raw[3:].strip() or None)
            pager = _PagerState()
            history_tokens = [None]
            items, _ = run_search(None)
            continue


        if raw.startswith("/from "):
            filters = replace(filters, from_addr=raw[6:].strip() or None)
            pager = _PagerState()
            history_tokens = [None]
            items, _ = run_search(None)
            continue

        if raw.startswith("/days "):
            n = _parse_int(raw[6:])
            if n is None or n < 0:
                print("Invalid days. Example: /days 30")
                continue
            filters = replace(filters, newer_than_days=n)
            pager = _PagerState()
            history_tokens = [None]
            items, _ = run_search(None)
            continue

        if raw.startswith("/unread "):
            val = raw[8:].strip().lower()
            if val not in ("on", "off"):
                print("Usage: /unread on|off")
                continue
            filters = replace(filters, unread_only=val == "on")
            pager = _PagerState()
            history_tokens = [None]
            items, _ = run_search(None)
            continue

        if raw.startswith("/inbox "):
            val = raw[7:].strip().lower()
            if val not in ("on", "off"):
                print("Usage: /inbox on|off")
                continue
            filters = replace(filters, inbox_only=val == "on")
            pager = _PagerState()
            history_tokens = [None]
            items, _ = run_search(None)
            continue

        if raw == "/show":
            items, _ = run_search(pager.page_token)
            continue

        if raw == "/next":
            if not pager.next_page_token:
                print("No next page.")
                continue
            history_tokens.append(pager.next_page_token)
            items, _ = run_search(pager.next_page_token)
            continue

        if raw == "/prev":
            # v1: best-effort by replaying from the start to previous token
            if len(history_tokens) <= 1:
                print("Already at first page.")
                continue
            history_tokens.pop()
            prev_token = history_tokens[-1]
            items, _ = run_search(prev_token)
            continue

        # Otherwise, attempt selection
        selected = _parse_selection(raw, max_n=len(items))
        if not selected:
            print("Unrecognized command. Type /help for commands.")
            continue

        chosen = [items[i - 1].message_id for i in selected]
        print("\nSelected message IDs:")
        for mid in chosen:
            print(f"  - {mid}")
        print("\nNext step: we will fetch headers for these examples and infer a durable newsletter rule.\n")
        return 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "Usage:\n"
            "  mailops configure\n"
            "\nCommands:\n"
            "  configure   interactive wizard to pick example newsletter emails\n"
        )
        return 0

    cmd = argv[0]
    if cmd == "configure":
        return configure()

    print(f"Unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
