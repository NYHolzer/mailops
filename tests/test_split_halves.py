from io import BytesIO

from pypdf import PdfReader
from pypdf import PdfWriter

from mailops.pdf.split_halves import split_pdf_into_vertical_halves  # top/bottom


def _make_test_pdf(num_pages: int = 2, width: int = 612, height: int = 792) -> bytes:
    """
    Create a simple blank PDF with N pages using pypdf only.
    Letter size defaults: 612 x 792 points.
    """
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=width, height=height)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_split_halves_doubles_page_count_and_preserves_page_size():
    src = _make_test_pdf(num_pages=3, width=600, height=800)

    out = split_pdf_into_vertical_halves(src)

    r_src = PdfReader(BytesIO(src))
    r_out = PdfReader(BytesIO(out))

    assert len(r_out.pages) == 2 * len(r_src.pages)

    # Each output page should preserve original page size
    src_w = float(r_src.pages[0].mediabox.width)
    src_h = float(r_src.pages[0].mediabox.height)

    for p in r_out.pages:
        assert float(p.mediabox.width) == src_w
        assert float(p.mediabox.height) == src_h


def test_split_halves_sets_crop_boxes_top_then_bottom_for_each_source_page():
    src = _make_test_pdf(num_pages=1, width=600, height=800)

    out = split_pdf_into_vertical_halves(src)
    r_out = PdfReader(BytesIO(out))
    assert len(r_out.pages) == 2

    top = r_out.pages[0]
    bottom = r_out.pages[1]

    # Original dimensions
    w = float(top.mediabox.width)
    h = float(top.mediabox.height)
    mid = h / 2.0

    # Crop boxes should differ
    # TOP: y from mid -> h
    assert float(top.cropbox.lower_left[0]) == 0.0
    assert float(top.cropbox.lower_left[1]) == mid
    assert float(top.cropbox.upper_right[0]) == w
    assert float(top.cropbox.upper_right[1]) == h

    # BOTTOM: y from 0 -> mid
    assert float(bottom.cropbox.lower_left[0]) == 0.0
    assert float(bottom.cropbox.lower_left[1]) == 0.0
    assert float(bottom.cropbox.upper_right[0]) == w
    assert float(bottom.cropbox.upper_right[1]) == mid
