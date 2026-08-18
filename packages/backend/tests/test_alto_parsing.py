"""Tesseract/ALTO word-suggestion parsing (OCR lexeme suggestions)."""

import pytest
from cadmus.infrastructure.ocr import OcrExecutionError, parse_alto_words

_NAMESPACED_ALTO = """<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v3#">
  <Layout>
    <Page WIDTH="1000" HEIGHT="1400">
      <PrintSpace>
        <TextBlock>
          <TextLine>
            <String CONTENT="слово" HPOS="10" VPOS="20"
                    WIDTH="100" HEIGHT="40" WC="0.92"/>
            <String CONTENT="друге" HPOS="120" VPOS="20"
                    WIDTH="90" HEIGHT="40" WC="0.5"/>
          </TextLine>
        </TextBlock>
      </PrintSpace>
    </Page>
  </Layout>
</alto>
"""

_UNNAMESPACED_ALTO = """<?xml version="1.0"?>
<alto>
  <Layout><Page WIDTH="500" HEIGHT="700"><PrintSpace><TextBlock><TextLine>
    <String CONTENT="test" HPOS="1" VPOS="2" WIDTH="30" HEIGHT="15"/>
  </TextLine></TextBlock></PrintSpace></Page></Layout>
</alto>"""


def test_parses_namespaced_alto_words_with_confidence() -> None:
    suggestions = parse_alto_words(_NAMESPACED_ALTO.encode("utf-8"))

    assert len(suggestions) == 2
    first, second = suggestions
    assert first.source_text == "слово"
    assert (first.x, first.y, first.width, first.height) == (10.0, 20.0, 100.0, 40.0)
    assert first.confidence == 0.92
    assert second.source_text == "друге"
    assert second.confidence == 0.5


def test_parses_alto_without_a_namespace_prefix() -> None:
    suggestions = parse_alto_words(_UNNAMESPACED_ALTO.encode("utf-8"))

    assert len(suggestions) == 1
    assert suggestions[0].source_text == "test"


def test_missing_wc_defaults_confidence_to_one() -> None:
    suggestions = parse_alto_words(_UNNAMESPACED_ALTO.encode("utf-8"))

    assert suggestions[0].confidence == 1.0


def test_out_of_range_wc_is_clamped() -> None:
    xml = (
        '<alto><String CONTENT="x" HPOS="0" VPOS="0" WIDTH="1" HEIGHT="1" '
        'WC="1.5"/></alto>'
    )
    suggestions = parse_alto_words(xml.encode("utf-8"))

    assert suggestions[0].confidence == 1.0


def test_skips_strings_with_empty_content() -> None:
    xml = '<alto><String CONTENT="" HPOS="1" VPOS="2" WIDTH="1" HEIGHT="1"/></alto>'

    assert parse_alto_words(xml.encode("utf-8")) == []


def test_skips_strings_with_non_positive_dimensions() -> None:
    xml = '<alto><String CONTENT="x" HPOS="1" VPOS="2" WIDTH="0" HEIGHT="1"/></alto>'

    assert parse_alto_words(xml.encode("utf-8")) == []


def test_skips_strings_missing_position_attributes() -> None:
    xml = '<alto><String CONTENT="x" WIDTH="1" HEIGHT="1"/></alto>'

    assert parse_alto_words(xml.encode("utf-8")) == []


def test_invalid_xml_raises_ocr_execution_error() -> None:
    with pytest.raises(OcrExecutionError):
        parse_alto_words(b"not xml at all")
