from io import BytesIO

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from mailops.pdf.text_density import page_text_stats, suggest_excludes_hybrid


def _make_pdf(pages) -> bytes:
    """
    pages: list[callable(canvas, w, h)] each draws on a page
    """
    buf = BytesIO()
    w, h = 600, 800
    c = canvas.Canvas(buf, pagesize=(w, h))
    for fn in pages:
        fn(c, w, h)
        c.showPage()
    c.save()
    return buf.getvalue()


def test_text_density_orders_pages_as_expected():
    def heavy(c, w, h):
        c.setFont("Helvetica", 10)
        y = h - 40
        for _ in range(60):
            c.drawString(30, y, "THIS IS A LOT OF TEXT " * 6)
            y -= 12

    def light(c, w, h):
        c.setFont("Helvetica", 14)
        c.drawString(40, h - 60, "Small headline")
        c.drawString(40, 50, "Footer")

    def blank(c, w, h):
        pass

    pdf = _make_pdf([heavy, light, blank])
    r = PdfReader(BytesIO(pdf))

    s0 = page_text_stats(r.pages[0], 0)
    s1 = page_text_stats(r.pages[1], 1)
    s2 = page_text_stats(r.pages[2], 2)

    assert s0.char_count > s1.char_count > s2.char_count
    assert s0.density > s1.density > s2.density


def test_hybrid_suggests_blank_and_light_pages():
    def heavy(c, w, h):
        c.setFont("Helvetica", 10)
        y = h - 40
        for _ in range(60):
            c.drawString(30, y, "THIS IS A LOT OF TEXT " * 6)
            y -= 12

    def light(c, w, h):
        c.setFont("Helvetica", 14)
        c.drawString(40, h - 60, "Small headline")
        c.drawString(40, 50, "Footer")

    def blank(c, w, h):
        pass

    pdf = _make_pdf([heavy, light, blank])
    r = PdfReader(BytesIO(pdf))

    stats = [page_text_stats(p, i) for i, p in enumerate(r.pages)]

    # Make the absolute thresholds intentionally strong so "heavy" is safe,
    # but "light" and "blank" get flagged.
    excludes = suggest_excludes_hybrid(
        stats,
        abs_min_chars=200,
        abs_min_density=20.0,
        rel_percentile=34.0,  # with 3 pages, this will capture the bottom-ish pages
    )

    assert 1 in excludes  # light
    assert 2 in excludes  # blank
    assert 0 not in excludes  # heavy
