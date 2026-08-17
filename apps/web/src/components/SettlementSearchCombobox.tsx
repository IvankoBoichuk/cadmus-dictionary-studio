import { useEffect, useState } from "react";

import {
  API,
  type AreaResponse,
  type CommunityResponse,
  type RegionResponse,
  type SettlementSuggestionResponse,
} from "../api";
import { useSettlementSearch } from "../hooks/useSettlementSearch";

/**
 * AC8: search the local settlement cache for a modern equivalent of a
 * historical geographic label. Picking a result only fills the form's
 * fields client-side (AC9) -- it never persists or confirms anything.
 */
export function SettlementSearchCombobox({
  dictionaryId,
  onSelect,
}: {
  dictionaryId: string;
  onSelect: (suggestion: SettlementSuggestionResponse) => void;
}) {
  const { filters, setFilters, state } = useSettlementSearch(dictionaryId);
  const [areas, setAreas] = useState<AreaResponse[]>([]);
  const [regions, setRegions] = useState<RegionResponse[]>([]);
  const [communities, setCommunities] = useState<CommunityResponse[]>([]);

  useEffect(() => {
    API.geography.listAreas().then(setAreas, () => setAreas([]));
  }, []);

  useEffect(() => {
    API.geography.listRegions(filters.areaId).then(setRegions, () => setRegions([]));
  }, [filters.areaId]);

  useEffect(() => {
    API.geography
      .listCommunities({ areaId: filters.areaId, regionId: filters.regionId })
      .then(setCommunities, () => setCommunities([]));
  }, [filters.areaId, filters.regionId]);

  return (
    <div className="settlement-search">
      <div className="form-field">
        <label htmlFor="settlement-search-query">Пошук населеного пункту</label>
        <input
          id="settlement-search-query"
          value={filters.query ?? ""}
          onChange={(event) =>
            setFilters((current) => ({ ...current, query: event.target.value }))
          }
          placeholder="Почніть вводити назву…"
        />
      </div>

      <div className="form-field">
        <label htmlFor="settlement-search-area">Область</label>
        <select
          id="settlement-search-area"
          value={filters.areaId ?? ""}
          onChange={(event) =>
            setFilters((current) => ({
              ...current,
              areaId: event.target.value || undefined,
              regionId: undefined,
              communityId: undefined,
            }))
          }
        >
          <option value="">Усі області</option>
          {areas.map((area) => (
            <option key={area.id} value={area.id}>
              {area.name}
            </option>
          ))}
        </select>
      </div>

      <div className="form-field">
        <label htmlFor="settlement-search-region">Район</label>
        <select
          id="settlement-search-region"
          value={filters.regionId ?? ""}
          onChange={(event) =>
            setFilters((current) => ({
              ...current,
              regionId: event.target.value || undefined,
              communityId: undefined,
            }))
          }
        >
          <option value="">Усі райони</option>
          {regions.map((region) => (
            <option key={region.id} value={region.id}>
              {region.name}
            </option>
          ))}
        </select>
      </div>

      <div className="form-field">
        <label htmlFor="settlement-search-community">Громада</label>
        <select
          id="settlement-search-community"
          value={filters.communityId ?? ""}
          onChange={(event) =>
            setFilters((current) => ({
              ...current,
              communityId: event.target.value || undefined,
            }))
          }
        >
          <option value="">Усі громади</option>
          {communities.map((community) => (
            <option key={community.id} value={community.id}>
              {community.name}
            </option>
          ))}
        </select>
      </div>

      {state.status === "searching" && <p role="status">Шукаємо…</p>}
      {state.status === "error" && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === "results" && (
        <ul className="settlement-search-results">
          {state.results.length === 0 && <li className="lede">Нічого не знайдено.</li>}
          {state.results.map((suggestion) => (
            <li key={suggestion.settlement_id}>
              <button
                type="button"
                className="secondary-button"
                onClick={() => onSelect(suggestion)}
              >
                {suggestion.title} ({suggestion.category}) — {suggestion.community_name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
