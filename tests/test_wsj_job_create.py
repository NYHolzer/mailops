from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from mailops.wsj.downloader import create_wsj_job_from_email_url


def _minimal_pdf_bytes() -> bytes:
    # A tiny valid-enough PDF for pypdf to read reliably.
    # (This is the smallest-ish “hello” PDF. Keep stable for tests.)
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n"
        b"trailer << /Size 4 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n"
    )


def test_create_wsj_job_writes_imposed_and_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Redirect JOBS_DIR by monkeypatching mailops.jobs.ROOT-derived path is hard,
    # so instead we patch new_job_dir to write under tmp_path.
    import mailops.jobs as jobs_mod

    def fake_new_job_dir(job_id: str) -> Path:
        d = tmp_path / job_id
        (d / "thumbs").mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(jobs_mod, "new_job_dir", fake_new_job_dir)

    # Mock download_from_email_link to write a PDF and return downloaded status
    import mailops.wsj.downloader as wsj_downloader_mod

    def fake_download_from_email_link(email_url, out_path, **kwargs):
        out_path.write_bytes(_minimal_pdf_bytes())
        return SimpleNamespace(
            status="downloaded",
            final_url="https://www.wsj.com/final",
            extracted_pdf_url="https://www.wsj.com/pdf",
            message="ok",
        )

    monkeypatch.setattr(wsj_downloader_mod, "download_from_email_link", fake_download_from_email_link)

    res = create_wsj_job_from_email_url(email_url="https://example.com/wsjtrack", job_id="wsj_test_job")

    assert res.ok is True
    assert (res.job_dir / "raw.pdf").exists()
    assert (res.job_dir / "imposed.pdf").exists()
    assert (res.job_dir / "review.json").exists()

    review = (res.job_dir / "review.json").read_text(encoding="utf-8")
    assert '"pages"' in review
    assert '"suggested_exclude_indices"' in review


def test_create_wsj_job_handles_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mailops.jobs as jobs_mod

    def fake_new_job_dir(job_id: str) -> Path:
        d = tmp_path / job_id
        (d / "thumbs").mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(jobs_mod, "new_job_dir", fake_new_job_dir)

    import mailops.wsj.downloader as wsj_downloader_mod

    def fake_download_from_email_link(email_url, out_path, **kwargs):
        return SimpleNamespace(
            status="blocked",
            final_url="https://blocked",
            extracted_pdf_url=None,
            message="blocked",
        )

    monkeypatch.setattr(wsj_downloader_mod, "download_from_email_link", fake_download_from_email_link)

    res = create_wsj_job_from_email_url(email_url="https://example.com/wsjtrack", job_id="wsj_blocked_job")
    assert res.ok is False
    assert (res.job_dir / "job_status.json").exists()
