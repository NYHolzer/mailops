from io import BytesIO

from pypdf import PdfReader, PdfWriter

from mailops.pdf.exclude import exclude_pages_by_index


def _make_blank_pdf(n: int = 5) -> bytes:
    w = PdfWriter()
    for _ in range(n):
        w.add_blank_page(width=600, height=800)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_exclude_pages_by_index_removes_expected_pages():
    src = _make_blank_pdf(5)
    out = exclude_pages_by_index(src, exclude=[1, 3])

    r = PdfReader(BytesIO(out))
    assert len(r.pages) == 3
