from __future__ import annotations

from io import BytesIO
from typing import Tuple
import copy

from pypdf import PdfReader, PdfWriter

LETTER_LANDSCAPE_W = 792.0  # 11in * 72
LETTER_LANDSCAPE_H = 612.0  # 8.5in * 72

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

def split_pdf_into_vertical_halves_imposed_letter_landscape(
    pdf_bytes: bytes,
    margin_pt: float = 18.0,
) -> bytes:
    """
    Print-safe split:
    - For each source page, create TWO output pages sized to Letter Landscape (792x612).
    - Each output page contains the cropped half, scaled and centered to fit within margins.

    This avoids relying on viewer/printer "fit to page" behavior and makes printing predictable.
    """
    if margin_pt < 0:
        raise ValueError("margin_pt must be >= 0")

    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()

    target_w = LETTER_LANDSCAPE_W
    target_h = LETTER_LANDSCAPE_H

    inner_w = target_w - 2.0 * margin_pt
    inner_h = target_h - 2.0 * margin_pt
    if inner_w <= 0 or inner_h <= 0:
        raise ValueError("margin_pt too large for letter landscape")

    for src_page in reader.pages:
        src_w = float(src_page.mediabox.width)
        src_h = float(src_page.mediabox.height)
        mid = src_h / 2.0

        # TOP HALF: crop y=[mid, src_h]
        top_view = copy.deepcopy(src_page)
        _set_cropbox(top_view, (0.0, mid, src_w, src_h))
        top_out = writer.add_blank_page(width=target_w, height=target_h)
        _impose_cropped_view_onto_letter(
            dest_page=top_out,
            view_page=top_view,
            crop_llx=0.0,
            crop_lly=mid,
            crop_w=src_w,
            crop_h=src_h - mid,
            inner_w=inner_w,
            inner_h=inner_h,
        )

        # BOTTOM HALF: crop y=[0, mid]
        bottom_view = copy.deepcopy(src_page)
        _set_cropbox(bottom_view, (0.0, 0.0, src_w, mid))
        bottom_out = writer.add_blank_page(width=target_w, height=target_h)
        _impose_cropped_view_onto_letter(
            dest_page=bottom_out,
            view_page=bottom_view,
            crop_llx=0.0,
            crop_lly=0.0,
            crop_w=src_w,
            crop_h=mid,
            inner_w=inner_w,
            inner_h=inner_h,
        )

    out = BytesIO()
    writer.write(out)
    return out.getvalue()

def _set_cropbox(page, box: Tuple[float, float, float, float]) -> None:
    x0, y0, x1, y1 = box
    page.cropbox.lower_left = (x0, y0)
    page.cropbox.upper_right = (x1, y1)

def _impose_cropped_view_onto_letter(
    dest_page,
    view_page,
    *,
    crop_llx: float,
    crop_lly: float,
    crop_w: float,
    crop_h: float,
    inner_w: float,
    inner_h: float,
) -> None:
    """
    Merge view_page onto dest_page with scaling/translation so the cropped region
    fills the available inner box (letter landscape minus margins), centered.

    We account for crop lower-left by translating by (-crop_llx, -crop_lly) before scaling.
    """
    # Scale to fit inside inner box
    scale = min(inner_w / crop_w, inner_h / crop_h)

    placed_w = crop_w * scale
    placed_h = crop_h * scale

    # Center within the letter page
    tx = (LETTER_LANDSCAPE_W - placed_w) / 2.0
    ty = (LETTER_LANDSCAPE_H - placed_h) / 2.0

    # Translate crop origin to (0,0), then scale, then translate into position.
    # Final translation becomes: tx + (-crop_llx)*scale, ty + (-crop_lly)*scale
    e = tx + (-crop_llx) * scale
    f = ty + (-crop_lly) * scale

    matrix = [scale, 0, 0, scale, e, f]

    _merge_transformed_page(dest_page, view_page, matrix)


def _merge_transformed_page(dest_page, src_page, matrix) -> None:
    """
    Compatibility shim for pypdf method naming across versions.
    """
    # pypdf newer: merge_transformed_page
    fn = getattr(dest_page, "merge_transformed_page", None)
    if callable(fn):
        fn(src_page, matrix)
        return

    # older: mergeTransformedPage
    fn = getattr(dest_page, "mergeTransformedPage", None)
    if callable(fn):
        fn(src_page, matrix)
        return

    raise RuntimeError("Your pypdf version lacks merge_transformed_page/mergeTransformedPage")