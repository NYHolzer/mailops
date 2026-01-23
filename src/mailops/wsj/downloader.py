# src/mailops/wsj/downloader.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

from mailops.jobs import new_job_dir, write_json
from mailops.wsj.download import DEFAULT_PROFILE_DIR, WsjDownloadResult, download_from_email_link


@dataclass(frozen=True)
class WsjJobCreateResult:
    ok: bool
    job_dir: Path
    wsj_result: WsjDownloadResult
    imposed_pdf: Optional[Path] = None
    review_json: Optional[Path] = None
    message: str = ""


def create_wsj_job_from_email_url(
    *,
    email_url: str,
    job_id: str | None = None,
    profile_dir: Path = DEFAULT_PROFILE_DIR,
    headed: bool = False,
    timeout_ms: int = 20000,
    debug_dir: Optional[Path] = None,
) -> WsjJobCreateResult:
    """
    End-to-end “job creator” for WSJ:

    - creates output/jobs/<job_id>/
    - downloads WSJ PDF into job dir
    - writes imposed.pdf (currently: the downloaded PDF)
    - writes review.json with a page list (and placeholder suggestions)

    Later steps:
    - auto ad exclusion -> suggested_exclude_indices
    - thumbs generation (optional)
    """
    if job_id is None:
        job_id = datetime.now().strftime("wsj_%Y%m%d_%H%M%S")

    job_dir = new_job_dir(job_id)

    raw_pdf = job_dir / "raw.pdf"
    imposed_pdf = job_dir / "imposed.pdf"
    review_json = job_dir / "review.json"

    wsj_res = download_from_email_link(
        email_url=email_url,
        out_path=raw_pdf,
        profile_dir=profile_dir,
        headed=headed,
        timeout_ms=timeout_ms,
        debug_dir=debug_dir,
    )

    if wsj_res.status != "downloaded" or not raw_pdf.exists():
        # Still write a small marker file for debugging
        write_json(
            job_dir / "job_status.json",
            {
                "job": job_dir.name,
                "ok": False,
                "status": wsj_res.status,
                "final_url": wsj_res.final_url,
                "pdf_url": wsj_res.extracted_pdf_url,
                "message": wsj_res.message,
            },
        )
        return WsjJobCreateResult(
            ok=False,
            job_dir=job_dir,
            wsj_result=wsj_res,
            message=f"WSJ download did not succeed (status={wsj_res.status}). See job_status.json",
        )

    # For now, “imposed” is just the original PDF. (We can add 2-up/split later if needed.)
    imposed_pdf.write_bytes(raw_pdf.read_bytes())

    # Build review.json expected by review_app.py
    reader = PdfReader(str(imposed_pdf))
    num_pages = len(reader.pages)

    pages = [{"page_id": f"p{i+1:03d}"} for i in range(num_pages)]

    review = {
        "job": job_dir.name,
        "source": {
            "type": "wsj_email_url",
            "email_url": email_url,
            "final_url": wsj_res.final_url,
            "pdf_url": wsj_res.extracted_pdf_url,
        },
        "pages": pages,
        # Placeholder: next commit will populate this using pdf/text_density heuristics
        "suggested_exclude_indices": [],
    }
    write_json(review_json, review)

    return WsjJobCreateResult(
        ok=True,
        job_dir=job_dir,
        wsj_result=wsj_res,
        imposed_pdf=imposed_pdf,
        review_json=review_json,
        message=f"Created WSJ job: {job_dir}",
    )
