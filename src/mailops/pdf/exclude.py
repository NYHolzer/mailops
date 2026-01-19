from __future__ import annotations

from io import BytesIO
from typing import Iterable, Set

from pypdf import PdfReader, PdfWriter


def exclude_pages_by_index(pdf_bytes: bytes, exclude: Iterable[int]) -> bytes:
    """
    Remove pages by 0-based index from a PDF.
    """
    exclude_set: Set[int] = set(exclude)

    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        if i in exclude_set:
            continue
        writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()
