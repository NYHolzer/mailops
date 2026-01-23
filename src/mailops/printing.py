# src/mailops/printing.py
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class PrintResult:
    ok: bool
    cmd: list[str]
    stdout: str = ""
    stderr: str = ""


def print_pdf(
    pdf_path: Path,
    *,
    printer: str | None = None,
    copies: int = 1,
    options: Sequence[str] = (),
) -> PrintResult:
    """
    Print a PDF using CUPS `lp`.

    - pdf_path: path to the PDF to print
    - printer: optional printer name (lp -d)
    - copies: number of copies (lp -n)
    - options: extra raw lp options, e.g. ["-o", "fit-to-page", "-o", "media=Letter"]

    Returns a PrintResult (so callers can log/debug and tests can assert).
    """
    pdf_path = Path(pdf_path).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if copies < 1:
        raise ValueError("copies must be >= 1")

    cmd: list[str] = ["lp", "-n", str(copies)]
    if printer:
        cmd.extend(["-d", printer])
    cmd.extend(list(options))
    cmd.append(str(pdf_path))

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return PrintResult(
        ok=(proc.returncode == 0),
        cmd=cmd,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )
