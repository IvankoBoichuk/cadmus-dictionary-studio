from uuid import uuid4

import pytest
from cadmus.geography import DecentralizationParseError
from cadmus.geography.domain import (
    parse_area,
    parse_community,
    parse_geo_json,
    parse_region,
)


def test_parse_area_happy_path() -> None:
    area = parse_area({"id": "12", "title": "Львівська область"})
    assert area.external_id == "12"
    assert area.name == "Львівська область"


def test_parse_area_accepts_integer_id() -> None:
    area = parse_area({"id": 12, "title": "Львівська область"})
    assert area.external_id == "12"


def test_parse_area_missing_name_raises() -> None:
    with pytest.raises(DecentralizationParseError):
        parse_area({"id": "12"})


def test_parse_area_blank_name_raises() -> None:
    with pytest.raises(DecentralizationParseError):
        parse_area({"id": "12", "title": "   "})


def test_parse_area_missing_id_raises() -> None:
    with pytest.raises(DecentralizationParseError):
        parse_area({"title": "Львівська область"})


def test_parse_area_rejects_non_object() -> None:
    with pytest.raises(DecentralizationParseError):
        parse_area("not-a-dict")  # type: ignore[arg-type]


def test_parse_region_happy_path() -> None:
    area_id = uuid4()
    region = parse_region({"id": "5", "title": "Личаківський район"}, area_id)
    assert region.external_id == "5"
    assert region.area_id == area_id


def test_parse_region_missing_required_field_raises() -> None:
    with pytest.raises(DecentralizationParseError):
        parse_region({"id": "5"}, uuid4())


def test_parse_community_happy_path_with_villages() -> None:
    area_id, region_id = uuid4(), uuid4()
    community, settlements = parse_community(
        {
            "id": "77",
            "title": "Брюховицька громада",
            "katottg": "UA46060070000012345",
            "koatuu": "4610136600",
            "website": "https://example.gov.ua",
            "indicators": {"population": 12000},
            "budget": {"budget_values": [1, 2, 3]},
            "villages": [
                {"title": "Малехів", "category": "село"},
                {"title": "Рудно", "category": "село"},
            ],
        },
        area_id,
        region_id,
    )
    assert community.external_id == "77"
    assert community.katottg == "UA46060070000012345"
    assert community.koatuu == "4610136600"
    assert community.indicators == {"population": 12000}
    assert community.budgets == {"budget_values": [1, 2, 3]}
    assert len(settlements) == 2
    assert {s.title for s in settlements} == {"Малехів", "Рудно"}
    assert all(s.community_id == community.id for s in settlements)


def test_parse_community_tolerates_missing_optional_fields() -> None:
    community, settlements = parse_community(
        {"id": "77", "title": "Брюховицька громада"}, uuid4(), uuid4()
    )
    assert community.katottg is None
    assert community.koatuu is None
    assert community.indicators is None
    assert community.budgets is None
    assert settlements == []


def test_parse_community_tolerates_wrong_typed_optional_field() -> None:
    community, _ = parse_community(
        {"id": "77", "title": "Брюховицька громада", "katottg": 12345}, uuid4(), uuid4()
    )
    assert community.katottg is None


def test_parse_community_missing_name_raises() -> None:
    with pytest.raises(DecentralizationParseError):
        parse_community({"id": "77"}, uuid4(), uuid4())


def test_parse_community_skips_village_missing_title() -> None:
    _, settlements = parse_community(
        {
            "id": "77",
            "title": "Брюховицька громада",
            "villages": [{"category": "село"}, {"title": "Рудно"}],
        },
        uuid4(),
        uuid4(),
    )
    assert len(settlements) == 1
    assert settlements[0].title == "Рудно"
    assert settlements[0].category == "unknown"


def test_parse_community_deduplicates_repeated_villages() -> None:
    _, settlements = parse_community(
        {
            "id": "77",
            "title": "Брюховицька громада",
            "villages": [
                {"title": "Малехів", "category": "село"},
                {"title": "Малехів", "category": "село"},
                {"title": "Малехів", "category": "селище"},
            ],
        },
        uuid4(),
        uuid4(),
    )
    assert len(settlements) == 2
    assert {(s.title, s.category) for s in settlements} == {
        ("Малехів", "село"),
        ("Малехів", "селище"),
    }


def test_parse_geo_json_point() -> None:
    community_id = uuid4()
    geometry = parse_geo_json(
        {"type": "Point", "coordinates": [24.03, 49.84]}, community_id
    )
    assert geometry.geometry_type == "Point"
    assert geometry.community_id == community_id


def test_parse_geo_json_polygon() -> None:
    geometry = parse_geo_json(
        {
            "type": "Polygon",
            "coordinates": [
                [[24.0, 49.8], [24.1, 49.8], [24.1, 49.9], [24.0, 49.8]],
            ],
        },
        uuid4(),
    )
    assert geometry.geometry_type == "Polygon"


def test_parse_geo_json_multipolygon() -> None:
    geometry = parse_geo_json(
        {
            "type": "MultiPolygon",
            "coordinates": [
                [[[24.0, 49.8], [24.1, 49.8], [24.1, 49.9], [24.0, 49.8]]],
            ],
        },
        uuid4(),
    )
    assert geometry.geometry_type == "MultiPolygon"


def test_parse_geo_json_unwraps_feature() -> None:
    geometry = parse_geo_json(
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [24.03, 49.84]},
            "properties": {},
        },
        uuid4(),
    )
    assert geometry.geometry_type == "Point"


def test_parse_geo_json_unwraps_feature_collection() -> None:
    geometry = parse_geo_json(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [24.03, 49.84]},
                }
            ],
        },
        uuid4(),
    )
    assert geometry.geometry_type == "Point"


def test_parse_geo_json_rejects_out_of_range_longitude() -> None:
    with pytest.raises(DecentralizationParseError):
        parse_geo_json({"type": "Point", "coordinates": [200.0, 49.84]}, uuid4())


def test_parse_geo_json_rejects_out_of_range_latitude() -> None:
    # A real [lat, lon] pair fed in as [lon, lat] (wrong order) surfaces as
    # an out-of-range latitude here, since Lviv's latitude (49.84) exceeds
    # the valid longitude range once misplaced as the second element.
    with pytest.raises(DecentralizationParseError):
        parse_geo_json({"type": "Point", "coordinates": [24.03, 149.84]}, uuid4())


def test_parse_geo_json_rejects_unknown_geometry_type() -> None:
    with pytest.raises(DecentralizationParseError):
        parse_geo_json({"type": "Sphere", "coordinates": [1, 2]}, uuid4())


def test_parse_geo_json_rejects_missing_coordinates() -> None:
    with pytest.raises(DecentralizationParseError):
        parse_geo_json({"type": "Point"}, uuid4())


def test_parse_geo_json_geometry_collection() -> None:
    geometry = parse_geo_json(
        {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Point", "coordinates": [24.03, 49.84]},
                {"type": "Point", "coordinates": [24.1, 49.9]},
            ],
        },
        uuid4(),
    )
    assert geometry.geometry_type == "GeometryCollection"
