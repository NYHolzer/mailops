from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .text_density import page_area_sq_in, extract_page_text


@dataclass(frozen=True)
class PageSignals:
    page_index: int
    char_count: int
    area_sq_in: float

    image_count: int
    largest_image_pixels: int
    total_image_pixels: int

    # Derived
    image_dominant: bool


def _iter_image_xobjects(page):
    """
    Yield (img_obj, width, height) for each /Image XObject on the page.
    """
    resources = page.get("/Resources") or {}
    xobj = resources.get("/XObject") if hasattr(resources, "get") else None
    if not xobj:
        return

    # xobj can be an IndirectObject or dict-like
    try:
        xobj = xobj.get_object()
    except Exception:
        pass

    for _, obj in (xobj.items() if hasattr(xobj, "items") else []):
        try:
            o = obj.get_object()
        except Exception:
            o = obj
        if not hasattr(o, "get"):
            continue
        if o.get("/Subtype") == "/Image":
            w = int(o.get("/Width") or 0)
            h = int(o.get("/Height") or 0)
            yield o, w, h


def page_signals(page, page_index: int, *, dominant_pixels_threshold: int = 1_000_000) -> PageSignals:
    text = extract_page_text(page)
    char_count = len("".join(text.split()))
    area = page_area_sq_in(page)

    image_count = 0
    largest = 0
    total = 0

    for _, w, h in _iter_image_xobjects(page) or []:
        image_count += 1
        px = w * h
        total += px
        if px > largest:
            largest = px

    # “dominant” heuristic: one big image likely means ad or full-bleed art.
    # Threshold is intentionally conservative; we’ll tune it using your review PDFs.
    image_dominant = largest >= dominant_pixels_threshold

    return PageSignals(
        page_index=page_index,
        char_count=char_count,
        area_sq_in=area,
        image_count=image_count,
        largest_image_pixels=largest,
        total_image_pixels=total,
        image_dominant=image_dominant,
    )
