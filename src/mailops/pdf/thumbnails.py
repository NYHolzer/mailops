from __future__ import annotations

from pathlib import Path
from typing import List

import fitz  # pymupdf


def render_thumbnails(pdf_bytes: bytes, out_dir: Path, *, zoom: float = 0.35) -> List[Path]:
    """
    Render each PDF page to a PNG thumbnail.
    zoom=0.35 is usually plenty for iPhone review without huge files.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    paths: List[Path] = []
    mat = fitz.Matrix(zoom, zoom)

    for i in range(doc.page_count):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        p = out_dir / f"page_{i:03d}.png"
        pix.save(str(p))
        paths.append(p)

    return paths
