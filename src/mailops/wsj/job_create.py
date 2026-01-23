from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

from mailops.jobs import new_job_dir, write_json
from mailops.wsj.download import DEFAULT_PROFILE_DIR, WsjDownloadResult, download_from_email_link
from mailops.pdf.text_density import suggest_excludes_hybrid  # adjust import if your function name differs


@dataclass(frozen=True)
class WsjJobResult:
    ok: bool
    job_dir: Path
    job_id: str
    wsj: WsjDownloadResult
    message: str = ""


def _slugify(s: str, max_len: int = 40) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        return "wsj"
    return s[:max_len].strip("-")


def _parse_yyyymmdd(d: str) -> date:
    # Accept "YYYY-MM-DD" or "YYYYMMDD"
    d = d.strip()
    if "-" in d:
        return datetime.strptime(d, "%Y-%m-%d").date()
    return datetime.strptime(d, "%Y%m%d").date()


def make_job_id(dt: date, subject: str) -> str:
    return f"wsj_{dt.strftime('%Y%m%d')}_{_slugify(subject)}"


def create_wsj_job_from_email_link(
    *,
    email_url: str,
    subject: str,
    email_date: date,
    profile_dir: Path = DEFAULT_PROFILE_DIR,
    headed: bool = False,
    timeout_ms: int = 20000,
    debug_dir: Optional[Path] = None,
    job_id: Optional[str] = None,
) -> WsjJobResult:
    """
    Create a printable-review job from a WSJ email tracking link.

    Artifacts written:
      - output/jobs/<job_id>/raw.pdf
      - output/jobs/<job_id>/imposed.pdf   (currently same as raw; later we can impose/split if needed)
      - output/jobs/<job_id>/review.json   (page list + suggested excludes placeholder)
    """
    job_id = job_id or make_job_id(email_date, subject)
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
        write_json(
            job_dir / "job_status.json",
            {
                "job": job_id,
                "ok": False,
                "status": wsj_res.status,
                "final_url": wsj_res.final_url,
                "pdf_url": wsj_res.extracted_pdf_url,
                "message": wsj_res.message,
            },
        )
        return WsjJobResult(
            ok=False,
            job_dir=job_dir,
            job_id=job_id,
            wsj=wsj_res,
            message=f"WSJ download did not succeed (status={wsj_res.status}). See job_status.json",
        )

    # For now, imposed == raw. Keep the naming because review_app expects imposed.pdf.
    imposed_pdf.write_bytes(raw_pdf.read_bytes())

    reader = PdfReader(str(imposed_pdf))
    pages = [{"page_id": f"p{i+1:03d}"} for i in range(len(reader.pages))]

    suggested = suggest_excludes_hybrid(imposed_pdf.read_bytes())

    write_json(
        review_json,
        {
            "job": job_id,
            "source": {
                "type": "wsj_email_link",
                "email_url": email_url,
                "subject": subject,
                "date": email_date.isoformat(),
                "final_url": wsj_res.final_url,
                "pdf_url": wsj_res.extracted_pdf_url,
            },
            "pages": pages,
            # Next step: fill this using your existing pdf/text_density heuristics to auto-suggest ad pages.
            "suggested_exclude_indices": sorted(suggested),
        },
    )

    return WsjJobResult(
        ok=True,
        job_dir=job_dir,
        job_id=job_id,
        wsj=wsj_res,
        message=f"Created job {job_id} at {job_dir}",
    )


def parse_date_for_cli(s: str) -> date:
    return _parse_yyyymmdd(s)
