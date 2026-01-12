from __future__ import annotations

from logging import config
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from ..models import EmailMessage

@dataclass(frozen=True)
class PrintConfig:
    printer_name: str
    title_prefix: str = "MailOps"

class PrintError(RuntimeError):
    pass

def email_to_pdf(msg: EmailMessage, output_path: Path) -> None:
    """
    Convert an email into a simple PDF suitable for printing.
    Keep it plain and robust; we can enhance formatting later.
    """ 
    c = canvas.Canvas(str(output_path), pagesize=LETTER)
    width, height = LETTER

    y = height - 50
    line_height = 14

    def draw_line(text: str) -> None:
        nonlocal y
        if y < 50:
            c.showPage()
            y = height - 50
        c.drawString(50, y, text[:120])
        y -= line_height

    draw_line(f"From: {msg.from_email}")
    draw_line(f"Subject: {msg.subject}")
    draw_line(f"Message-ID: {msg.message_id}")
    draw_line("-"*90)

    body = (msg.content.text or "").strip() or (msg.snippet or "")
    for raw_line in body.splitlines():
        #naive wrap: split long lines
        line = raw_line.strip()
        while len(line) > 120:
            draw_line(line[:120])
            line = line[120:]
        draw_line(line)
    
    c.save()

def print_pdf(printer_name: str, pdf_path: Path, job_title: Optional[str] = None) -> None:
    if not pdf_path.exists():
        raise PrintError(f"PDF file does not exist: {pdf_path}")
    
    cmd = ["lp", "-d", printer_name]
    if job_title:
        cmd += ["-t", job_title]
    cmd.append(str(pdf_path))

    try: 
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        raise PrintError(f"Printing failed: {e.stderr.strip()}") from e
    

def print_email(msg: EmailMessage, config: PrintConfig) -> None:
    job_title = f"{config.title_prefix}: {msg.subject}".strip()[:120]

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "email_print.pdf"
        email_to_pdf(msg, pdf_path)
        print_pdf(config.printer_name, pdf_path, job_title=job_title)

def get_available_printers() -> list[str]:
    """
    List available printers using lpstat.
    Returns a list of printer names.
    """
    try:
        # lpstat -a lists accepting destinations
        # Format: "Printer_Name accepting requests since ..."
        res = subprocess.run(
            ["lpstat", "-a"], 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        printers = []
        for line in res.stdout.splitlines():
            parts = line.split()
            if parts:
                printers.append(parts[0])
        return sorted(printers)
    except FileNotFoundError:
        # lpstat not installed
        return []
    except subprocess.CalledProcessError:
        # Error running command
        return []