# tests/test_printing.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mailops.printing import print_pdf


def test_print_pdf_builds_lp_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = "request id is Printer-123 (1 file(s))"
    fake_proc.stderr = ""

    def fake_run(cmd, capture_output, text, check):
        assert capture_output is True
        assert text is True
        assert check is False
        return fake_proc

    monkeypatch.setattr("mailops.printing.subprocess.run", fake_run)

    res = print_pdf(
        pdf,
        printer="HP_LaserJet",
        copies=2,
        options=["-o", "fit-to-page", "-o", "media=Letter"],
    )

    assert res.ok is True
    # Command should be stable and predictable
    assert res.cmd[:1] == ["lp"]
    assert ["-n", "2"] == res.cmd[1:3]
    assert ["-d", "HP_LaserJet"] == res.cmd[3:5]
    assert res.cmd[-1].endswith("x.pdf")


def test_print_pdf_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdf"
    with pytest.raises(FileNotFoundError):
        print_pdf(missing)


def test_print_pdf_invalid_copies_raises(tmp_path: Path) -> None:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    with pytest.raises(ValueError):
        print_pdf(pdf, copies=0)
