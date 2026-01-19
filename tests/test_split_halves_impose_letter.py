from io import BytesIO

from pypdf import PdfReader

from reportlab.pdfgen import canvas

from mailops.pdf.split_halves import split_pdf_into_vertical_halves_imposed_letter_landscape


LETTER_LANDSCAPE_W = 792  # 11in * 72
LETTER_LANDSCAPE_H = 612  # 8.5in * 72


def _make_pdf_with_text(num_pages: int = 1, page_w: int = 600, page_h: int = 800) -> bytes:
    """
    Create a PDF with actual content (text) so we can verify
    the imposed output isn't structurally empty.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))

    for i in range(num_pages):
        c.setFont("Helvetica", 18)
        c.drawString(40, page_h - 60, f"TOP CONTENT p{i+1}")
        c.drawString(40, 40, f"BOTTOM CONTENT p{i+1}")
        c.showPage()

    c.save()
    return buf.getvalue()


def test_imposed_halves_double_page_count_and_are_letter_landscape():
    src = _make_pdf_with_text(num_pages=3, page_w=600, page_h=800)

    out = split_pdf_into_vertical_halves_imposed_letter_landscape(src, margin_pt=18)

    r_src = PdfReader(BytesIO(src))
    r_out = PdfReader(BytesIO(out))

    assert len(r_out.pages) == 2 * len(r_src.pages)

    for p in r_out.pages:
        assert float(p.mediabox.width) == LETTER_LANDSCAPE_W
        assert float(p.mediabox.height) == LETTER_LANDSCAPE_H
        # cropbox should match mediabox for predictable printing
        assert float(p.cropbox.width) == LETTER_LANDSCAPE_W
        assert float(p.cropbox.height) == LETTER_LANDSCAPE_H


def test_imposed_output_pages_have_content_streams():
    src = _make_pdf_with_text(num_pages=1, page_w=600, page_h=800)

    out = split_pdf_into_vertical_halves_imposed_letter_landscape(src, margin_pt=18)
    r_out = PdfReader(BytesIO(out))

    assert len(r_out.pages) == 2

    # Structural check: output pages should have contents after merge
    for p in r_out.pages:
        assert p.get("/Contents") is not None
