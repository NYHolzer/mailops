from pathlib import Path

from mailops.actions.print_action import PrintConfig, email_to_pdf, print_email
from mailops.models import EmailMessage


def test_email_to_pdf_writes_pdf(tmp_path: Path):
    msg = EmailMessage(
        message_id="m1",
        thread_id="t1",
        from_email="sender@example.com",
        subject="Hello",
        date=None,
        snippet="snippet",
        body_text="Line 1\nLine 2",
    )
    out = tmp_path / "out.pdf"
    email_to_pdf(msg, out)
    assert out.exists()
    data = out.read_bytes()
    assert data[:4] == b"%PDF"


def test_print_email_invokes_lp(monkeypatch):
    calls = {}

    def fake_run(cmd, check, stdout, stderr, text):
        calls["cmd"] = cmd

        class R:
            stdout = "ok"
            stderr = ""

        return R()

    monkeypatch.setattr("mailops.actions.print_action.subprocess.run", fake_run)

    msg = EmailMessage(
        message_id="m2",
        thread_id=None,
        from_email="sender@example.com",
        subject="Print Me",
        date=None,
        snippet="",
        body_text="Body",
    )
    cfg = PrintConfig(printer_name="HP577dw")

    print_email(msg, cfg)

    assert calls["cmd"][0] == "lp"
    assert "-d" in calls["cmd"]
    assert "HP577dw" in calls["cmd"]
