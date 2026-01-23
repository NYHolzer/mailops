from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


DEFAULT_PROFILE_DIR = Path("~/.config/mailops/wsj_profile").expanduser()


@dataclass(frozen=True)
class WsjDownloadResult:
    status: str  # "downloaded" | "blocked" | "needs_manual"
    final_url: str
    extracted_pdf_url: Optional[str] = None
    message: str = ""


_BLOCK_MARKERS = [
    "access blocked",
    "unusual activity",
    "automated activity",
]


def _looks_blocked(html_lower: str) -> bool:
    return any(m in html_lower for m in _BLOCK_MARKERS)


def _extract_state_pdf_url(url: str) -> Optional[str]:
    """
    If we land on a DowJones SSO authorize URL, it may contain:
      state=https%3A%2F%2Fwww.wsj.com%2Fedition%2Fresources%2Fdocuments%2Fprint%2F...pdf
    We try to extract the decoded-looking PDF URL if present.
    """
    m = re.search(r"state=([^&]+)", url)
    if not m:
        return None
    state = m.group(1)

    from urllib.parse import unquote

    decoded = unquote(state)
    if decoded.lower().endswith(".pdf") and decoded.startswith("http"):
        return decoded
    return None

def _collect_pdf_urls_from_network(page) -> list[str]:
    """
    Best-effort: observe network traffic and return any URLs that look like PDFs.
    WSJ often fetches PDFs via XHR/fetch rather than linking them directly.
    """
    seen: list[str] = []

    def consider(url: str) -> None:
        u = (url or "").strip()
        if not u:
            return
        if ".pdf" in u.lower():
            if u not in seen:
                seen.append(u)

    page.on("request", lambda req: consider(req.url))
    page.on("response", lambda resp: consider(resp.url))

    return seen


def download_from_email_link(
    email_url: str,
    out_path: Path,
    profile_dir: Path = DEFAULT_PROFILE_DIR,
    headed: bool = False,
    timeout_ms: int = 20000,
    debug_dir: Optional[Path] = None,
) -> WsjDownloadResult:
    """
    Given the WSJ email tracking link, follow redirects in a persistent profile,
    then attempt to download the PDF.

    This does NOT attempt to bypass blocks. If blocked, returns status="blocked".
    """
    out_path = out_path.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    profile_dir = profile_dir.expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    def dump_debug(page, name: str) -> None:
        if not debug_dir:
            return
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / f"{name}.url.txt").write_text(page.url, encoding="utf-8")
        (debug_dir / f"{name}.html").write_text(page.content(), encoding="utf-8")
        try:
            page.screenshot(path=str(debug_dir / f"{name}.png"), full_page=True)
        except Exception:
            pass

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=(not headed),
            accept_downloads=True,
            viewport={"width": 1400, "height": 900},
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            if page.url == "about:blank":
                page = ctx.new_page()
            
            pdf_urls_seen = _collect_pdf_urls_from_network(page)

            # Try to navigate, capturing an immediate download if it occurs.
            try:
                try:
                    with page.expect_download(timeout=timeout_ms) as dl_info:
                        page.goto(email_url, wait_until="domcontentloaded")
                    download = dl_info.value
                    download.save_as(str(out_path))
                    return WsjDownloadResult(
                        status="downloaded",
                        final_url=page.url,
                        message=f"Downloaded during navigation: {out_path}",
                    )
                except Exception as e:
                    # Sometimes Playwright throws before expect_download captures it.
                    if "Download is starting" in str(e):
                        # Capture the already-started download and save it.
                        with page.expect_download(timeout=timeout_ms) as dl_info2:
                            pass
                        download = dl_info2.value
                        download.save_as(str(out_path))
                        return WsjDownloadResult(
                            status="downloaded",
                            final_url=page.url,
                            message=f"Downloaded during navigation (post-capture): {out_path}",
                        )
                    raise
            except PlaywrightTimeoutError:
                # No download event; proceed normally.
                page.goto(email_url, wait_until="domcontentloaded")

            # Otherwise, proceed normally.
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
            page.wait_for_timeout(1200)

            dump_debug(page, "landing")

            html_lower = page.content().lower()
            if _looks_blocked(html_lower):
                return WsjDownloadResult(
                    status="blocked",
                    final_url=page.url,
                    message="Dow Jones blocked automated browsing for this session/network. Use headed bootstrap login or manual download fallback.",
                )

            # If we land on SSO authorize URL, try extracting PDF from state
            pdf_url = _extract_state_pdf_url(page.url)

            # If no state-derived PDF, try to find any .pdf links on the page
            if not pdf_url:
                for a in page.query_selector_all("a[href]"):
                    href = a.get_attribute("href") or ""
                    if ".pdf" in href.lower():
                        pdf_url = href
                        break

            if not pdf_url:
                # As a last attempt, see if a download is triggered by obvious buttons.
                # Keep it gentle: one pass.
                download_obj = None

                def on_download(d):
                    nonlocal download_obj
                    download_obj = d

                page.on("download", on_download)

                for label in ["Download", "PDF", "Print"]:
                    loc = page.get_by_text(label)
                    if loc.count() > 0:
                        try:
                            loc.first.click(timeout=2000)
                            page.wait_for_timeout(2000)
                        except Exception:
                            pass
                        break

                if download_obj is not None:
                    download_obj.save_as(str(out_path))
                    return WsjDownloadResult(
                        status="downloaded",
                        final_url=page.url,
                        message=f"Downloaded via browser download event: {out_path}",
                    )
                
                # Fallback: if we saw a PDF in network traffic, try the most recent one.
                if pdf_urls_seen:
                    candidate = pdf_urls_seen[-1]
                    resp = page.request.get(candidate)
                    if resp.ok:
                        out_path.write_bytes(resp.body())
                        return WsjDownloadResult(
                            status="downloaded",
                            final_url=page.url,
                            extracted_pdf_url=candidate,
                            message=f"Saved from network-observed PDF URL: {out_path}",
                        )

                return WsjDownloadResult(
                    status="needs_manual",
                    final_url=page.url,
                    message="Could not locate a PDF link or download trigger. Try headed mode, or manually download the PDF and place it at the expected location.",
                )

            # Handle relative PDF links
            if pdf_url.startswith("/"):
                base = page.url.split("/", 3)[:3]
                pdf_url = "/".join(base) + pdf_url

            # Fetch using authenticated browser context
            resp = page.request.get(pdf_url)
            if not resp.ok:
                return WsjDownloadResult(
                    status="needs_manual",
                    final_url=page.url,
                    extracted_pdf_url=pdf_url,
                    message=f"Found PDF URL but request failed (HTTP {resp.status}). Try headed bootstrap login, then retry.",
                )

            out_path.write_bytes(resp.body())
            return WsjDownloadResult(
                status="downloaded",
                final_url=page.url,
                extracted_pdf_url=pdf_url,
                message=f"Saved: {out_path}",
            )

        finally:
            ctx.close()
