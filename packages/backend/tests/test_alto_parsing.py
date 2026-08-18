"""Tesseract/ALTO dictionary-entry suggestion parsing (OCR lexeme suggestions)."""

import pytest
from cadmus.infrastructure.ocr import OcrExecutionError, parse_alto_entries

_NAMESPACED_ALTO = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v3#">
  <Layout>
    <Page WIDTH="1000" HEIGHT="1400">
      <PrintSpace>
        <TextBlock HPOS="10" VPOS="20" WIDTH="200" HEIGHT="80">
          <TextLine>
            <String CONTENT="слово" HPOS="10" VPOS="20"
                    WIDTH="100" HEIGHT="40" WC="0.92"/>
            <String CONTENT="друге" HPOS="120" VPOS="20"
                    WIDTH="90" HEIGHT="40" WC="0.5"/>
          </TextLine>
        </TextBlock>
        <TextBlock HPOS="10" VPOS="120" WIDTH="150" HEIGHT="40">
          <TextLine>
            <String CONTENT="третє" HPOS="10" VPOS="120" WIDTH="90" HEIGHT="40"/>
          </TextLine>
        </TextBlock>
      </PrintSpace>
    </Page>
  </Layout>
</alto>
"""

_UNNAMESPACED_ALTO = """<?xml version="1.0"?>
<alto>
  <Layout><Page WIDTH="500" HEIGHT="700"><PrintSpace>
    <TextBlock HPOS="1" VPOS="2" WIDTH="30" HEIGHT="15">
      <TextLine>
        <String CONTENT="test" HPOS="1" VPOS="2" WIDTH="30" HEIGHT="15"/>
      </TextLine>
    </TextBlock>
  </PrintSpace></Page></Layout>
</alto>"""


def test_parses_namespaced_alto_entries_grouped_by_text_block() -> None:
    suggestions = parse_alto_entries(_NAMESPACED_ALTO.encode("utf-8"))

    assert len(suggestions) == 2
    first, second = suggestions
    assert first.source_text == "слово друге"
    assert (first.x, first.y, first.width, first.height) == (10.0, 20.0, 200.0, 80.0)
    assert first.confidence == pytest.approx(0.71)
    assert second.source_text == "третє"


def test_parses_alto_without_a_namespace_prefix() -> None:
    suggestions = parse_alto_entries(_UNNAMESPACED_ALTO.encode("utf-8"))

    assert len(suggestions) == 1
    assert suggestions[0].source_text == "test"


def test_missing_wc_defaults_confidence_to_one() -> None:
    suggestions = parse_alto_entries(_UNNAMESPACED_ALTO.encode("utf-8"))

    assert suggestions[0].confidence == 1.0


def test_out_of_range_wc_is_clamped() -> None:
    xml = (
        '<alto><TextBlock HPOS="0" VPOS="0" WIDTH="1" HEIGHT="1"><TextLine>'
        '<String CONTENT="x" HPOS="0" VPOS="0" WIDTH="1" HEIGHT="1" WC="1.5"/>'
        "</TextLine></TextBlock></alto>"
    )
    suggestions = parse_alto_entries(xml.encode("utf-8"))

    assert suggestions[0].confidence == 1.0


def test_skips_blocks_with_no_non_empty_words() -> None:
    xml = (
        '<alto><TextBlock HPOS="1" VPOS="2" WIDTH="1" HEIGHT="1"><TextLine>'
        '<String CONTENT="" HPOS="1" VPOS="2" WIDTH="1" HEIGHT="1"/>'
        "</TextLine></TextBlock></alto>"
    )

    assert parse_alto_entries(xml.encode("utf-8")) == []


def test_skips_blocks_with_non_positive_dimensions() -> None:
    xml = (
        '<alto><TextBlock HPOS="1" VPOS="2" WIDTH="0" HEIGHT="1"><TextLine>'
        '<String CONTENT="x" HPOS="1" VPOS="2" WIDTH="1" HEIGHT="1"/>'
        "</TextLine></TextBlock></alto>"
    )

    assert parse_alto_entries(xml.encode("utf-8")) == []


def test_skips_blocks_missing_position_attributes() -> None:
    xml = (
        '<alto><TextBlock WIDTH="1" HEIGHT="1"><TextLine>'
        '<String CONTENT="x" HPOS="1" VPOS="2" WIDTH="1" HEIGHT="1"/>'
        "</TextLine></TextBlock></alto>"
    )

    assert parse_alto_entries(xml.encode("utf-8")) == []


def test_invalid_xml_raises_ocr_execution_error() -> None:
    with pytest.raises(OcrExecutionError):
        parse_alto_entries(b"not xml at all")
