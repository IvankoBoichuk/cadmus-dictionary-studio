"""BH-30 geography reference-data domain objects and parsers.

Pure, framework-free normalization of ``decentralization.ua``'s GraphQL and
REST responses into local dataclasses. Every parser is tolerant of missing
optional fields and unexpected types (AC16) and only raises
``DecentralizationParseError`` when a field the local model genuinely
requires (an id, a name, valid geometry) is absent or malformed.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

_GEOMETRY_TYPES: frozenset[str] = frozenset(
    {
        "Point",
        "MultiPoint",
        "LineString",
        "MultiLineString",
        "Polygon",
        "MultiPolygon",
        "GeometryCollection",
    }
)


class GeographySyncStatus(StrEnum):
    """Outcome of one BH-30 reference-data sync run for one entity type."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class GeographyEntityType(StrEnum):
    """The kind of reference data a ``SyncRun`` covers."""

    AREA = "area"
    REGION = "region"
    COMMUNITY = "community"
    GEOMETRY = "geometry"


class DecentralizationParseError(ValueError):
    """Raised when a ``decentralization.ua`` response entity cannot be
    normalized: a required field (id, name) is missing or the wrong type,
    or GeoJSON geometry is malformed or has out-of-range coordinates.
    """


@dataclass
class Area:
    """One oblast, cached locally from ``decentralization.ua``'s ``areas``."""

    id: UUID
    external_id: str
    name: str
    last_synced_at: datetime


@dataclass
class Region:
    """One raion, cached locally from ``decentralization.ua``'s ``regions``."""

    id: UUID
    external_id: str
    name: str
    area_id: UUID
    last_synced_at: datetime


@dataclass
class Settlement:
    """One ``community.villages`` entry.

    The API assigns no external id to a village, so identity is a local
    natural key: ``(community_id, title, category)``.
    """

    id: UUID
    community_id: UUID
    title: str
    category: str


@dataclass
class Community:
    """One territorial hromada, with its nested settlements resolved
    separately (see ``parse_community``'s return tuple).
    """

    id: UUID
    external_id: str
    name: str
    area_id: UUID
    region_id: UUID
    last_synced_at: datetime
    katottg: str | None = None
    koatuu: str | None = None
    admin_center_name: str | None = None
    website: str | None = None
    indicators: dict[str, object] | list[object] | None = None
    budgets: dict[str, object] | list[object] | None = None


@dataclass
class CommunityGeometry:
    """One community's cached, schema-validated GeoJSON geometry."""

    id: UUID
    community_id: UUID
    geometry_type: str
    geometry: dict[str, object]
    fetched_at: datetime


@dataclass
class SyncRun:
    """One AC17 sync-metadata record for one entity type."""

    id: UUID
    entity_type: GeographyEntityType
    source: str
    started_at: datetime
    status: GeographySyncStatus
    records_synced: int = 0
    records_failed: int = 0
    completed_at: datetime | None = None
    error_message: str | None = None


def _require_external_id(raw: dict[str, object], context: str) -> str:
    value = raw.get("id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    raise DecentralizationParseError(f"{context} response is missing a valid 'id'")


def _require_str(raw: dict[str, object], key: str, *, context: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DecentralizationParseError(
            f"{context} response is missing required field '{key}'"
        )
    return value.strip()


def _optional_str(raw: dict[str, object], key: str) -> str | None:
    value = raw.get(key)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _optional_json_value(
    raw: dict[str, object], key: str
) -> dict[str, object] | list[object] | None:
    value = raw.get(key)
    if isinstance(value, dict) or isinstance(value, list):
        return value
    return None


def _admin_center_name(raw: dict[str, object]) -> str | None:
    direct = _optional_str(raw, "admin_center_name")
    if direct is not None:
        return direct
    # decentralization.ua's real schema returns ``center`` as a plain string
    # (the settlement name), not a nested object.
    center = raw.get("center")
    if isinstance(center, dict):
        return _optional_str(center, "name")
    return _optional_str(raw, "center")


def parse_area(raw: dict[str, object], *, synced_at: datetime | None = None) -> Area:
    """Normalize one entry of the ``areas``/``area(id)`` GraphQL response."""
    if not isinstance(raw, dict):
        raise DecentralizationParseError("area response must be an object")
    return Area(
        id=uuid4(),
        external_id=_require_external_id(raw, "area"),
        name=_require_str(raw, "title", context="area"),
        last_synced_at=synced_at or datetime.now(UTC),
    )


def parse_region(
    raw: dict[str, object], area_id: UUID, *, synced_at: datetime | None = None
) -> Region:
    """Normalize one entry of the ``regions``/``region(id)`` GraphQL response."""
    if not isinstance(raw, dict):
        raise DecentralizationParseError("region response must be an object")
    return Region(
        id=uuid4(),
        external_id=_require_external_id(raw, "region"),
        name=_require_str(raw, "title", context="region"),
        area_id=area_id,
        last_synced_at=synced_at or datetime.now(UTC),
    )


def _parse_settlements(raw_villages: object, community_id: UUID) -> list[Settlement]:
    if not isinstance(raw_villages, list):
        return []
    settlements: list[Settlement] = []
    seen_keys: set[tuple[str, str]] = set()
    for entry in raw_villages:
        if not isinstance(entry, dict):
            continue
        title = _optional_str(entry, "title")
        if title is None:
            continue
        # A village with a missing/unexpected-type category is still kept
        # (AC16 graceful null handling) under a sentinel category.
        category = _optional_str(entry, "category") or "unknown"
        # The real API occasionally lists the same village twice for one
        # community; (title, category) is the settlement's unique key, so
        # duplicates within one response must be collapsed before upsert.
        key = (title, category)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        settlements.append(
            Settlement(
                id=uuid4(), community_id=community_id, title=title, category=category
            )
        )
    return settlements


def parse_community(
    raw: dict[str, object],
    area_id: UUID,
    region_id: UUID,
    *,
    synced_at: datetime | None = None,
) -> tuple[Community, list[Settlement]]:
    """Normalize one ``communities``/``community(id)`` GraphQL entry.

    Returns the community together with its nested ``villages`` parsed into
    ``Settlement`` rows, since both are sourced from the same response.
    """
    if not isinstance(raw, dict):
        raise DecentralizationParseError("community response must be an object")
    community_id = uuid4()
    community = Community(
        id=community_id,
        external_id=_require_external_id(raw, "community"),
        name=_require_str(raw, "title", context="community"),
        area_id=area_id,
        region_id=region_id,
        katottg=_optional_str(raw, "katottg"),
        koatuu=_optional_str(raw, "koatuu"),
        admin_center_name=_admin_center_name(raw),
        website=_optional_str(raw, "site") or _optional_str(raw, "website"),
        indicators=_optional_json_value(raw, "indicators"),
        budgets=_optional_json_value(raw, "budgets")
        or _optional_json_value(raw, "budget"),
        last_synced_at=synced_at or datetime.now(UTC),
    )
    settlements = _parse_settlements(raw.get("villages"), community_id)
    return community, settlements


def _is_position(node: object) -> bool:
    return (
        isinstance(node, list)
        and len(node) in (2, 3)
        and all(
            isinstance(value, int | float) and not isinstance(value, bool)
            for value in node
        )
    )


def _validate_position(position: list[int | float]) -> None:
    longitude, latitude = position[0], position[1]
    if not (-180 <= longitude <= 180):
        raise DecentralizationParseError(
            f"longitude {longitude!r} out of range; "
            "expected [longitude, latitude] order"
        )
    if not (-90 <= latitude <= 90):
        raise DecentralizationParseError(
            f"latitude {latitude!r} out of range; expected [longitude, latitude] order"
        )


def _validate_coordinates(node: object) -> None:
    if _is_position(node):
        _validate_position(node)  # type: ignore[arg-type]
        return
    if isinstance(node, list) and node:
        for child in node:
            _validate_coordinates(child)
        return
    raise DecentralizationParseError(f"malformed GeoJSON coordinates: {node!r}")


def _validate_geometry_dict(geometry: dict[str, object]) -> None:
    geometry_type = geometry.get("type")
    if geometry_type not in _GEOMETRY_TYPES:
        raise DecentralizationParseError(
            f"unknown GeoJSON geometry type: {geometry_type!r}"
        )
    if geometry_type == "GeometryCollection":
        geometries = geometry.get("geometries")
        if not isinstance(geometries, list) or not geometries:
            raise DecentralizationParseError(
                "GeometryCollection is missing non-empty 'geometries'"
            )
        for member in geometries:
            if not isinstance(member, dict):
                raise DecentralizationParseError(
                    "geometry collection member must be an object"
                )
            _validate_geometry_dict(member)
        return
    coordinates = geometry.get("coordinates")
    if coordinates is None:
        raise DecentralizationParseError(
            f"{geometry_type} geometry is missing 'coordinates'"
        )
    _validate_coordinates(coordinates)


def parse_geo_json(raw: dict[str, object], community_id: UUID) -> CommunityGeometry:
    """Normalize and validate one community's GeoJSON geometry response
    (AC6): geometry type must be a known GeoJSON type, and every coordinate
    pair must be in ``[longitude, latitude]`` order.
    """
    if not isinstance(raw, dict):
        raise DecentralizationParseError("geo_json response must be an object")

    geometry: object = raw
    if raw.get("type") == "Feature":
        geometry = raw.get("geometry")
    elif raw.get("type") == "FeatureCollection":
        features = raw.get("features")
        if not isinstance(features, list) or not features:
            raise DecentralizationParseError("FeatureCollection has no features")
        first_feature = features[0]
        if not isinstance(first_feature, dict):
            raise DecentralizationParseError("feature must be an object")
        geometry = first_feature.get("geometry")

    if not isinstance(geometry, dict):
        raise DecentralizationParseError(
            "geo_json response is missing a geometry object"
        )

    _validate_geometry_dict(geometry)
    return CommunityGeometry(
        id=uuid4(),
        community_id=community_id,
        geometry_type=str(geometry["type"]),
        geometry=geometry,
        fetched_at=datetime.now(UTC),
    )
