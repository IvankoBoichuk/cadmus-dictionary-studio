"""``decentralization.ua`` GraphQL/REST adapter (AC3-AC6, AC16).

Hand-rolled GraphQL over ``httpx`` (no GraphQL client dependency): every
query is a plain string template posted as ``{"query": ...}``. Requests are
bounded by a configured timeout and retried a bounded number of times with
exponential backoff, but only for transient failures (connection errors,
timeouts, 5xx) -- a 4xx or a malformed response body fails immediately as a
``DecentralizationApiResponseError`` since retrying it cannot help.

Field names below were verified against the live ``decentralization.ua``
GraphQL endpoint via introspection (its real schema diverges from the shape
originally assumed from the ticket text alone): entities expose ``title``
rather than ``name``, ``area_id``/``region_id`` are flat scalar fields
rather than nested ``{id, name}`` objects, the community website field is
called ``site``, and singular lookups (``area(id: String)``,
``region(id: String)``, ``community(id: String)``) take a **string** id
argument even though the corresponding list entries return an ``Int`` id.
Most importantly, the bulk ``communities`` query returns the ``Community``
type, which has no ``villages``/``budgets`` fields at all -- only the
singular ``community(id)`` query (return type ``NewCommunity``) exposes
them. ``list_communities()`` therefore fetches the bulk id list first and
then issues one singular ``community(id)`` request per community to obtain
its villages and budgets; for the ~1,500 communities currently published
this is a one-off cost paid only by the manual ``make sync-geography`` CLI
run, never by a request-latency-sensitive path.
"""

import time
from collections.abc import Callable

import httpx

from cadmus.config import Settings
from cadmus.geography.ports import (
    DecentralizationApiResponseError,
    DecentralizationApiUnavailableError,
)

_AREAS_QUERY = """
query {
  areas {
    id
    title
  }
}
"""

_REGIONS_QUERY = """
query {
  regions {
    id
    title
    area_id
  }
}
"""

_COMMUNITY_IDS_QUERY = """
query {
  communities {
    id
  }
}
"""

_COMMUNITY_QUERY = """
query($id: String!) {
  community(id: $id) {
    id
    title
    katottg
    koatuu
    site
    center
    area_id
    area_name
    region_id
    region_name
    villages { title category }
    budgets { id title }
  }
}
"""

_RETRYABLE_STATUS_THRESHOLD = 500


class HttpxDecentralizationApiClient:
    """``httpx``-backed ``DecentralizationApiClient`` implementation."""

    def __init__(
        self,
        *,
        graphql_url: str,
        rest_base_url: str,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        self._graphql_url = graphql_url
        self._rest_base_url = rest_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    def list_areas(self) -> list[dict[str, object]]:
        data = self._graphql(_AREAS_QUERY)
        return self._list_field(data, "areas")

    def get_area(self, external_id: str) -> dict[str, object] | None:
        return self._find_by_id(self.list_areas(), external_id)

    def list_regions(self) -> list[dict[str, object]]:
        data = self._graphql(_REGIONS_QUERY)
        return self._list_field(data, "regions")

    def get_region(self, external_id: str) -> dict[str, object] | None:
        return self._find_by_id(self.list_regions(), external_id)

    def list_communities(self) -> list[dict[str, object]]:
        ids_data = self._graphql(_COMMUNITY_IDS_QUERY)
        communities: list[dict[str, object]] = []
        for entry in self._list_field(ids_data, "communities"):
            external_id = entry.get("id")
            if external_id is None:
                continue
            full = self.get_community(str(external_id))
            if full is not None:
                communities.append(full)
        return communities

    def get_community(self, external_id: str) -> dict[str, object] | None:
        data = self._graphql(_COMMUNITY_QUERY, variables={"id": external_id})
        value = data.get("community")
        if value is None:
            return None
        if not isinstance(value, dict):
            raise DecentralizationApiResponseError(
                "GraphQL response field 'community' is not an object"
            )
        return value

    def get_community_geo_json(self, community_id: str) -> dict[str, object] | None:
        url = f"{self._rest_base_url}/communities/{community_id}/geo_json"
        response = self._request(lambda: httpx.get(url, timeout=self._timeout_seconds))
        if response.status_code == 404:
            return None
        payload = self._json_object(response)
        return payload

    @staticmethod
    def _list_field(data: dict[str, object], key: str) -> list[dict[str, object]]:
        value = data.get(key)
        if not isinstance(value, list):
            raise DecentralizationApiResponseError(
                f"GraphQL response field {key!r} is not a list"
            )
        return [entry for entry in value if isinstance(entry, dict)]

    @staticmethod
    def _find_by_id(
        entries: list[dict[str, object]], external_id: str
    ) -> dict[str, object] | None:
        for entry in entries:
            if str(entry.get("id")) == external_id:
                return entry
        return None

    def _graphql(
        self, query: str, variables: dict[str, object] | None = None
    ) -> dict[str, object]:
        body: dict[str, object] = {"query": query}
        if variables is not None:
            body["variables"] = variables
        response = self._request(
            lambda: httpx.post(
                self._graphql_url,
                json=body,
                timeout=self._timeout_seconds,
            )
        )
        payload = self._json_object(response)
        errors = payload.get("errors")
        if errors:
            raise DecentralizationApiResponseError(f"GraphQL errors: {errors!r}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise DecentralizationApiResponseError(
                "GraphQL response is missing a 'data' object"
            )
        return data

    def _json_object(self, response: httpx.Response) -> dict[str, object]:
        try:
            payload = response.json()
        except ValueError as error:
            raise DecentralizationApiResponseError(
                f"response body is not valid JSON: {error}"
            ) from error
        if not isinstance(payload, dict):
            raise DecentralizationApiResponseError("response body is not a JSON object")
        return payload

    def _request(self, send: Callable[[], httpx.Response]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = send()
            except (httpx.TimeoutException, httpx.ConnectError) as error:
                last_error = error
            else:
                if response.status_code < 400:
                    return response
                if response.status_code < _RETRYABLE_STATUS_THRESHOLD:
                    raise DecentralizationApiResponseError(
                        f"request failed with status {response.status_code}: "
                        f"{response.text[:200]}"
                    )
                last_error = DecentralizationApiUnavailableError(
                    f"request failed with status {response.status_code}"
                )

            if attempt < self._max_retries:
                time.sleep(min(0.5 * 2**attempt, 5.0))

        raise DecentralizationApiUnavailableError(
            f"request failed after {self._max_retries + 1} attempt(s)"
        ) from last_error


def create_decentralization_api_client(
    settings: Settings,
) -> HttpxDecentralizationApiClient:
    """Build the ``decentralization.ua`` adapter from environment settings."""
    return HttpxDecentralizationApiClient(
        graphql_url=settings.geography_api_graphql_url,
        rest_base_url=settings.geography_api_rest_base_url,
        timeout_seconds=settings.geography_api_timeout_seconds,
        max_retries=settings.geography_api_max_retries,
    )
