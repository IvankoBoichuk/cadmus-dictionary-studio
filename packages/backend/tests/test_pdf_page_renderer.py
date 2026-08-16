from io import BytesIO

import pytest
from cadmus.infrastructure.sources import PypdfiumPageRenderer
from cadmus.sources import InvalidPdfError
from pypdf import PdfWriter

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _pdf_with_pages(*sizes: tuple[float, float]) -> bytes:
    writer = PdfWriter()
    for width, height in sizes:
        writer.add_blank_page(width=width, height=height)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_render_pages_yields_one_png_per_page_in_order() -> None:
    renderer = PypdfiumPageRenderer()

    pages = list(renderer.render_pages(BytesIO(_pdf_with_pages((72, 72), (72, 72)))))

    assert [page.page_index for page in pages] == [0, 1]
    assert all(page.content.startswith(_PNG_SIGNATURE) for page in pages)


def test_render_pages_scales_dimensions_to_the_target_dpi() -> None:
    renderer = PypdfiumPageRenderer()

    (page,) = list(renderer.render_pages(BytesIO(_pdf_with_pages((72, 144)))))

    # 72pt = 1 inch at the PDF's native 72 DPI; rendered at 200 DPI.
    assert (page.width, page.height) == (200, 400)


def test_render_pages_rejects_a_file_that_only_looks_like_a_pdf() -> None:
    renderer = PypdfiumPageRenderer()
    spoofed = BytesIO(b"%PDF-1.4\nthis is not a real pdf body at all")

    with pytest.raises(InvalidPdfError):
        list(renderer.render_pages(spoofed))


def test_render_pages_rejects_empty_content() -> None:
    renderer = PypdfiumPageRenderer()

    with pytest.raises(InvalidPdfError):
        list(renderer.render_pages(BytesIO(b"")))
