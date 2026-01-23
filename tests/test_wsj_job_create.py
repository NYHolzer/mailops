from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from mailops.wsj.job_create import create_wsj_job_from_email_link, make_job_id


def _minimal_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n"
        b"trailer << /Size 4 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n"
    )


def test_make_job_id_human_friendly() -> None:
    jid = make_job_id(date(2026, 1, 23), "The WSJ Morning: Markets & Rates!")
    assert jid.startswith("wsj_20260123_")
    assert "markets-rates" in jid


def test_create_job_writes_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mailops.jobs as jobs_mod

    def fake_new_job_dir(job_id: str) -> Path:
        d = tmp_path / job_id
        (d / "thumbs").mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(jobs_mod, "new_job_dir", fake_new_job_dir)

    import mailops.wsj.job_create as jc

    def fake_download_from_email_link(email_url, out_path, **kwargs):
        out_path.write_bytes(_minimal_pdf_bytes())
        return SimpleNamespace(
            status="downloaded",
            final_url="https://www.wsj.com/final",
            extracted_pdf_url="https://www.wsj.com/pdf",
            message="ok",
        )

    monkeypatch.setattr(jc, "download_from_email_link", fake_download_from_email_link)

    res = create_wsj_job_from_email_link(
        email_url="https://example.com/wsjtrack",
        subject="WSJ Print Edition",
        email_date=date(2026, 1, 23),
    )

    assert res.ok is True
    assert (res.job_dir / "raw.pdf").exists()
    assert (res.job_dir / "imposed.pdf").exists()
    assert (res.job_dir / "review.json").exists()


def test_create_job_handles_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mailops.jobs as jobs_mod

    def fake_new_job_dir(job_id: str) -> Path:
        d = tmp_path / job_id
        (d / "thumbs").mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(jobs_mod, "new_job_dir", fake_new_job_dir)

    import mailops.wsj.job_create as jc

    def fake_download_from_email_link(email_url, out_path, **kwargs):
        return SimpleNamespace(
            status="blocked",
            final_url="https://blocked",
            extracted_pdf_url=None,
            message="blocked",
        )

    monkeypatch.setattr(jc, "download_from_email_link", fake_download_from_email_link)

    res = create_wsj_job_from_email_link(
        email_url="https://example.com/wsjtrack",
        subject="WSJ Print Edition",
        email_date=date(2026, 1, 23),
    )

    assert res.ok is False
    assert (res.job_dir / "job_status.json").exists()

def test_create_job_writes_suggestions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mailops.jobs as jobs_mod

    def fake_new_job_dir(job_id: str) -> Path:
        d = tmp_path / job_id
        (d / "thumbs").mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(jobs_mod, "new_job_dir", fake_new_job_dir)

    import mailops.wsj.job_create as jc

    def fake_download_from_email_link(email_url, out_path, **kwargs):
        out_path.write_bytes(_minimal_pdf_bytes())
        return SimpleNamespace(
            status="downloaded",
            final_url="https://www.wsj.com/final",
            extracted_pdf_url="https://www.wsj.com/pdf",
            message="ok",
        )

    monkeypatch.setattr(jc, "download_from_email_link", fake_download_from_email_link)

    # Patch suggestion logic to a deterministic output
    import mailops.pdf.text_density as td
    monkeypatch.setattr(td, "suggest_exclude_indices", lambda pdf_bytes: {0, 2})

    res = jc.create_wsj_job_from_email_link(
        email_url="https://example.com/wsjtrack",
        subject="WSJ Print Edition",
        email_date=date(2026, 1, 23),
    )
    review = (res.job_dir / "review.json").read_text(encoding="utf-8")
    assert '"suggested_exclude_indices": [\n    0,\n    2\n  ]' in review
