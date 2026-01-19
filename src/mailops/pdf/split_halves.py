from __future__ import annotations

from io import BytesIO
from typing import Tuple
import copy

from pypdf import PdfReader, PdfWriter


def split_pdf_into_vertical_halves(pdf_bytes: bytes) -> bytes:
    """
    Split each PDF page into two pages:
      - first: TOP half (cropped)
      - second: BOTTOM half (cropped)

    Output keeps the same page size (MediaBox) as the original pages,
    but uses CropBox to show only the desired half.
    """
    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()

    for page in reader.pages:
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        mid = h / 2.0

        top = copy.deepcopy(page)
        _set_cropbox(top, (0.0, mid, w, h))
        writer.add_page(top)

        bottom = copy.deepcopy(page)
        _set_cropbox(bottom, (0.0, 0.0, w, mid))
        writer.add_page(bottom)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _set_cropbox(page, box: Tuple[float, float, float, float]) -> None:
    x0, y0, x1, y1 = box
    page.cropbox.lower_left = (x0, y0)
    page.cropbox.upper_right = (x1, y1)
