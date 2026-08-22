"""Real Tesseract/ALTO contract test -- skipped unless the binary is present."""

import shutil
from io import BytesIO

import pytest
from cadmus.infrastructure.ocr import TesseractAltoOcrProvider
from PIL import Image, ImageDraw

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="requires the tesseract-ocr binary"
)


def _synthetic_page_image() -> bytes:
    image = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 30), "HELLO WORLD", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_tesseract_locates_words_with_plausible_pixel_coordinates() -> None:
    provider = TesseractAltoOcrProvider(timeout_seconds=25.0)

    suggestions = provider.suggest_words(_synthetic_page_image(), language="eng")

    assert len(suggestions) >= 1
    joined = " ".join(s.source_text for s in suggestions).upper()
    assert "HELLO" in joined or "WORLD" in joined
    for suggestion in suggestions:
        assert 0 <= suggestion.x <= 400
        assert 0 <= suggestion.y <= 100
        assert suggestion.width > 0
        assert suggestion.height > 0
        assert 0.0 <= suggestion.confidence <= 1.0
