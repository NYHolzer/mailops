import sys
from dataclasses import dataclass, replace
from typing import Optional

from .gmail_client import GmailMessageSummary
from .manager import Manager, SearchResult
from .search import SearchFilters


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
    mgr = Manager()

    filters = SearchFilters(text=None, from_addr=None, newer_than_days=7, unread_only=True, inbox_only=True)
    pager = _PagerState()
    history_tokens: list[Optional[str]] = [None]  # best-effort /prev by replaying pages

    def run_search(page_token: Optional[str]) -> SearchResult:
        res = mgr.search(filters, max_results=20, page_token=page_token)
        print(f"\nQuery: {mgr._rules_engine} (Filters applied internally)\n") # debug info
        pager.page_token = page_token
        pager.next_page_token = res.next_page_token
        _print_results(res.items)
        return res

    print("\nMailOps Configure (v1)\n")
    _help()

    last_res = run_search(None)
    items = last_res.items

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
            last_res = run_search(None)
            items = last_res.items
            continue


        if raw.startswith("/from "):
            filters = replace(filters, from_addr=raw[6:].strip() or None)
            pager = _PagerState()
            history_tokens = [None]
            last_res = run_search(None)
            items = last_res.items
            continue

        if raw.startswith("/days "):
            n = _parse_int(raw[6:])
            if n is None or n < 0:
                print("Invalid days. Example: /days 30")
                continue
            filters = replace(filters, newer_than_days=n)
            pager = _PagerState()
            history_tokens = [None]
            last_res = run_search(None)
            items = last_res.items
            continue

        if raw.startswith("/unread "):
            val = raw[8:].strip().lower()
            if val not in ("on", "off"):
                print("Usage: /unread on|off")
                continue
            filters = replace(filters, unread_only=val == "on")
            pager = _PagerState()
            history_tokens = [None]
            last_res = run_search(None)
            items = last_res.items
            continue

        if raw.startswith("/inbox "):
            val = raw[7:].strip().lower()
            if val not in ("on", "off"):
                print("Usage: /inbox on|off")
                continue
            filters = replace(filters, inbox_only=val == "on")
            pager = _PagerState()
            history_tokens = [None]
            last_res = run_search(None)
            items = last_res.items
            continue

        if raw == "/show":
            last_res = run_search(pager.page_token)
            items = last_res.items
            continue

        if raw == "/next":
            if not pager.next_page_token:
                print("No next page.")
                continue
            history_tokens.append(pager.next_page_token)
            last_res = run_search(pager.next_page_token)
            items = last_res.items
            continue

        if raw == "/prev":
            # v1: best-effort by replaying from the start to previous token
            if len(history_tokens) <= 1:
                print("Already at first page.")
                continue
            history_tokens.pop()
            prev_token = history_tokens[-1]
            last_res = run_search(prev_token)
            items = last_res.items
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


def run_automation(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="mailops run")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would happen")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    args = parser.parse_args(argv)
    
    mgr = Manager()
    print("Checking for automation matches...")
    plan = mgr.get_automation_plan()

    if not plan:
        print("No matches found.")
        return 0

    print(f"\nPlanned Actions ({len(plan)}):")
    print(f"{'ACTION':<10} | {'RULE':<15} | {'SUBJECT':<40} | {'FROM'}")
    print("-" * 80)
    for item, rule in plan:
        subj = (item.subject or "")[:38]
        # Clean newlines from subject for display
        subj = subj.replace("\n", " ").replace("\r", "")
        print(f"{rule.action:<10} | {rule.name[:15]:<15} | {subj:<40} | {item.from_email}")
    print("-" * 80)

    if args.dry_run:
        print("\nDry run complete. No actions taken.")
        return 0

    if not args.yes:
        # Interactive check
        try:
            q = input(f"\nExecute these {len(plan)} actions? [y/N] ").strip().lower()
        except EOFError:
            q = "n"
            
        if q != 'y':
            print("Aborted.")
            return 0

    print("\nExecuting...")
    mgr.execute_automation_plan(plan)
    print("Done.")
    return 0


def search_cli(argv: list[str]) -> int:
    # helper for one-off search from CLI args
    # mailops search --from "foo" --days 3
    import argparse
    parser = argparse.ArgumentParser(prog="mailops search")
    parser.add_argument("--query", "-q", help="Full text query")
    parser.add_argument("--sender", "--from", help="Sender address or domain")
    parser.add_argument("--days", type=int, help="Newer than N days")
    parser.add_argument("--unread", action="store_true", help="Unread only (default false if omitted)")
    parser.add_argument("--archive", action="store_true", help="Archive results")
    parser.add_argument("--delete", action="store_true", help="Delete results (trash)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run actions")

    args = parser.parse_args(argv)

    filters = SearchFilters(
        text=args.query,
        from_addr=args.sender,
        newer_than_days=args.days,
        unread_only=args.unread,
        inbox_only=True
    )

    mgr = Manager()
    res = mgr.search(filters, max_results=50)
    
    _print_results(res.items)

    action = "archive" if args.archive else ("delete" if args.delete else None)
    
    if action and res.items:
        print(f"\nPerforming action '{action}' on {len(res.items)} items...")
        for item in res.items:
            if not args.dry_run:
                mgr.execute_action(item.message_id, action, "cli-bulk-action")
            else:
                print(f"[Dry Run] Would {action} {item.message_id}")
    
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "Usage:\n"
            "  mailops configure\n"
            "  mailops run [--dry-run]\n"
            "  mailops search [options]\n"
            "  mailops ui [port]\n"
        )
        return 0

    cmd = argv[0]
    rest = argv[1:]

    if cmd == "configure":
        return configure()
    if cmd == "run":
        return run_automation(rest)
    if cmd == "search":
        return search_cli(rest)
    if cmd == "ui":
        from .web_server import run_server
        port = 8000
        if rest and rest[0].isdigit():
            port = int(rest[0])
        run_server(port)
        return 0

    print(f"Unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
