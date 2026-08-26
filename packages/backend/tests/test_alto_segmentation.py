"""BH-148 ALTO segmentation (experimental variant 1): word-level parsing and
padded-crop geometry -- ``TesseractAltoOcrProvider.segment_region``'s two
pure building blocks."""

from io import BytesIO

import pytest
from cadmus.infrastructure.ocr import (
    _DEFAULT_SEGMENT_MIN_PADDING,
    _DEFAULT_SEGMENT_PADDING_RATIO,
    OcrExecutionError,
    _padded_and_clamped_box,
    _union_box,
    crop_region,
    parse_alto_words,
)
from PIL import Image

_ALTO_TWO_LINES = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v3#">
  <Layout>
    <Page WIDTH="500" HEIGHT="200">
      <PrintSpace>
        <TextBlock HPOS="0" VPOS="0" WIDTH="300" HEIGHT="60">
          <TextLine>
            <String CONTENT="слово" HPOS="10" VPOS="20"
                    WIDTH="40" HEIGHT="10" WC="0.9"/>
            <String CONTENT="друге" HPOS="55" VPOS="20"
                    WIDTH="40" HEIGHT="10" WC="0.4"/>
          </TextLine>
          <TextLine>
            <String CONTENT="третє" HPOS="10" VPOS="35" WIDTH="40" HEIGHT="10"/>
          </TextLine>
        </TextBlock>
      </PrintSpace>
    </Page>
  </Layout>
</alto>
"""


def test_parse_alto_words_returns_one_segment_per_word_in_reading_order() -> None:
    segments = parse_alto_words(_ALTO_TWO_LINES.encode("utf-8"))

    assert [segment.text for segment in segments] == ["слово", "друге", "третє"]
    assert [segment.index for segment in segments] == [0, 1, 2]


def test_parse_alto_words_translates_positions_by_the_given_offset() -> None:
    segments = parse_alto_words(
        _ALTO_TWO_LINES.encode("utf-8"), offset_x=100.0, offset_y=50.0
    )

    first = segments[0]
    assert (first.x, first.y, first.width, first.height) == (110.0, 70.0, 40.0, 10.0)


def test_parse_alto_words_keeps_each_words_own_confidence() -> None:
    segments = parse_alto_words(_ALTO_TWO_LINES.encode("utf-8"))

    assert segments[0].confidence == pytest.approx(0.9)
    assert segments[1].confidence == pytest.approx(0.4)
    assert segments[2].confidence == 1.0  # missing WC defaults to 1.0


def test_parse_alto_words_skips_empty_strings() -> None:
    xml = (
        '<alto><TextLine><String CONTENT="" HPOS="0" VPOS="0" '
        'WIDTH="1" HEIGHT="1"/></TextLine></alto>'
    )

    assert parse_alto_words(xml.encode("utf-8")) == []


def test_parse_alto_words_invalid_xml_raises_ocr_execution_error() -> None:
    with pytest.raises(OcrExecutionError):
        parse_alto_words(b"not xml at all")


def test_union_box_covers_all_given_boxes() -> None:
    box = _union_box([(10.0, 10.0, 20.0, 20.0), (0.0, 40.0, 5.0, 5.0)])

    # spans from the leftmost/topmost corner to the rightmost/bottommost
    assert box == (0.0, 10.0, 30.0, 35.0)


def test_padded_and_clamped_box_pads_each_axis_by_its_own_size() -> None:
    box = _padded_and_clamped_box(
        (100.0, 100.0, 20.0, 10.0),
        image_width=1000,
        image_height=1000,
        padding_ratio=0.5,
        min_padding=5.0,
    )

    # width 20 * 0.5 -> padding_x 10 (beats the 5px floor);
    # height 10 * 0.5 -> padding_y 5 (equals the floor) -- NOT the width's
    # padding applied to both axes, which is the BH-148 bug this guards:
    # a wide-but-short box (typical dictionary entry) must not get a huge
    # vertical margin derived from its width, or the crop swallows a
    # neighboring entry above/below.
    assert box == (90.0, 95.0, 40.0, 20.0)


def test_padded_and_clamped_box_uses_the_minimum_padding_floor() -> None:
    box = _padded_and_clamped_box(
        (100.0, 100.0, 4.0, 4.0),
        image_width=1000,
        image_height=1000,
        padding_ratio=0.2,
        min_padding=40.0,
    )

    assert box == (60.0, 60.0, 84.0, 84.0)


def test_padded_and_clamped_box_clamps_to_image_bounds() -> None:
    box = _padded_and_clamped_box(
        (0.0, 0.0, 10.0, 10.0),
        image_width=100,
        image_height=100,
        padding_ratio=20.0,  # deliberately huge, to force clamping on all sides
        min_padding=0.0,
    )

    assert box == (0.0, 0.0, 100.0, 100.0)


def _solid_png(width: int, height: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_crop_region_returns_a_padded_crop_and_its_origin() -> None:
    image_bytes = _solid_png(500, 500)

    cropped_bytes, origin_x, origin_y = crop_region(
        image_bytes,
        [(100.0, 100.0, 50.0, 20.0)],
        padding_ratio=0.2,
        min_padding=10.0,
    )

    with Image.open(BytesIO(cropped_bytes)) as cropped:
        # padding = max(10, 50*0.2) = 10 on every side
        assert cropped.size == (70, 40)
    assert (origin_x, origin_y) == (90.0, 90.0)


def test_crop_region_clamps_padding_at_the_image_edge() -> None:
    image_bytes = _solid_png(200, 200)

    cropped_bytes, origin_x, origin_y = crop_region(
        image_bytes,
        [(0.0, 0.0, 10.0, 10.0)],
        padding_ratio=0.0,
        min_padding=50.0,
    )

    with Image.open(BytesIO(cropped_bytes)) as cropped:
        assert cropped.size == (60, 60)
    assert (origin_x, origin_y) == (0.0, 0.0)


def test_crop_region_covers_the_union_of_multiple_boxes() -> None:
    image_bytes = _solid_png(500, 500)

    _cropped_bytes, origin_x, origin_y = crop_region(
        image_bytes,
        [(100.0, 100.0, 10.0, 10.0), (300.0, 100.0, 10.0, 10.0)],
        padding_ratio=0.0,
        min_padding=0.0,
    )

    assert (origin_x, origin_y) == (100.0, 100.0)


def test_crop_region_requires_at_least_one_box() -> None:
    with pytest.raises(ValueError, match="at least one box"):
        crop_region(_solid_png(10, 10), [])


def test_default_padding_stays_well_under_a_line_height_for_a_wide_entry() -> None:
    # Regression test for a real BH-148 bug: a typical multi-line
    # dictionary-entry box (much wider than tall) got the *same* padding
    # on both axes, derived from its width -- vertically that's several
    # times a line's height, so the crop (and therefore OCR segmentation
    # handed to the AI) swallowed the entire neighboring entry above/below,
    # and the AI extracted that neighbor's words instead of this entry's.
    box = _padded_and_clamped_box(
        (555.0, 515.0, 508.0, 179.0),  # a real reported entry's fragment box
        image_width=2000,
        image_height=2000,
        padding_ratio=_DEFAULT_SEGMENT_PADDING_RATIO,
        min_padding=_DEFAULT_SEGMENT_MIN_PADDING,
    )

    _left, top, _width, _height = box
    vertical_padding = 515.0 - top
    # well under a plausible line height (~30px for a 179px/5-line block)
    assert vertical_padding < 20
