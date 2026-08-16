from io import BytesIO

import pytest
from cadmus.infrastructure.sources import PyPdfInspector
from cadmus.sources import InvalidPdfError
from pypdf import PdfWriter


def _pdf_with_pages(count: int) -> bytes:
    writer = PdfWriter()
    for _ in range(count):
        writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_page_count_extracts_the_number_of_pages() -> None:
    inspector = PyPdfInspector()

    assert inspector.page_count(BytesIO(_pdf_with_pages(1))) == 1
    assert inspector.page_count(BytesIO(_pdf_with_pages(7))) == 7


def test_page_count_rejects_a_file_that_only_looks_like_a_pdf() -> None:
    inspector = PyPdfInspector()
    spoofed = BytesIO(b"%PDF-1.4\nthis is not a real pdf body at all")

    with pytest.raises(InvalidPdfError):
        inspector.page_count(spoofed)


def test_page_count_rejects_empty_content() -> None:
    inspector = PyPdfInspector()

    with pytest.raises(InvalidPdfError):
        inspector.page_count(BytesIO(b""))
