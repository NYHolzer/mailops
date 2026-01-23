from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


DEFAULT_PROFILE_DIR = Path("~/.config/mailops/wsj_profile").expanduser()


def _default_user_agent() -> str:
    # A stable, realistic UA helps reduce bot suspicion a bit.
    # Keep it simple and consistent.
    return (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )


def bootstrap_login(
    url: str,
    profile_dir: Path = DEFAULT_PROFILE_DIR,
    headed: bool = True,
) -> None:
    """
    Open a persistent browser profile and allow the user to complete WSJ/DowJones login manually.
    This persists cookies/session into profile_dir so later automation can reuse it.

    The function blocks until the user presses Enter in the terminal.
    """
    profile_dir = profile_dir.expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Allow override via env, but keep CLI param as primary.
    os.environ.setdefault("MAILOPS_WSJ_PROFILE_DIR", str(profile_dir))

    print(f"[mailops] Using persistent profile: {profile_dir}")
    print("[mailops] A browser window will open. Complete login manually.")
    print("[mailops] When you can access Today's Edition normally, return here and press Enter.\n")

    with sync_playwright() as p:
        # launch_persistent_context is the key: it stores cookies/local storage in profile_dir.
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=not headed,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            viewport={"width": 1400, "height": 900},
            user_agent=_default_user_agent(),
            locale="en-US",
        )

        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded")

            # Optional: basic “unusual activity” detection, for user clarity.
            # We do NOT attempt to bypass; we just print a hint.
            try:
                page.wait_for_timeout(1000)
                content = page.content().lower()
                if "access blocked" in content or "unusual activity" in content:
                    print("[mailops] Detected an 'Access blocked / unusual activity' page.")
                    print("[mailops] If this persists, slow down and ensure JS is enabled, avoid devtools, etc.\n")
            except Exception:
                pass

            input("[mailops] Press Enter here once you are logged in and can view the edition... ")

        finally:
            context.close()

    print("[mailops] Done. Session data saved. Subsequent runs should reuse this profile.\n")


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Bootstrap WSJ login using a persistent Playwright profile.")
    ap.add_argument("--url", required=True, help="WSJ Today's Edition link (from email).")
    ap.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help=f"Persistent profile directory (default: {DEFAULT_PROFILE_DIR})",
    )
    ap.add_argument(
        "--headed",
        action="store_true",
        help="Run with visible browser window (recommended).",
    )
    ap.add_argument(
        "--headless",
        action="store_true",
        help="Run headless (NOT recommended for login).",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)

    headed = True
    if args.headless:
        headed = False
    if args.headed:
        headed = True

    bootstrap_login(
        url=args.url,
        profile_dir=Path(args.profile_dir),
        headed=headed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
