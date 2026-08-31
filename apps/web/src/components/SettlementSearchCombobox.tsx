import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  API,
  type AreaResponse,
  type CommunityResponse,
  type RegionResponse,
  type SettlementSuggestionResponse,
} from "../api";
import { useSettlementSearch } from "../hooks/useSettlementSearch";

/** Radix `Select` не приймає порожнє значення, тож "усі …" кодуємо сентинелом. */
const ALL = "__all__";

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
    <div className="flex flex-col gap-3">
      <div className="form-field">
        <Label htmlFor="settlement-search-query">Пошук населеного пункту</Label>
        <Input
          id="settlement-search-query"
          value={filters.query ?? ""}
          onChange={(event) =>
            setFilters((current) => ({ ...current, query: event.target.value }))
          }
          placeholder="Почніть вводити назву…"
        />
      </div>

      <div className="form-field">
        <Label htmlFor="settlement-search-area">Область</Label>
        <Select
          value={filters.areaId ?? ALL}
          onValueChange={(value) =>
            setFilters((current) => ({
              ...current,
              areaId: value === ALL ? undefined : value,
              regionId: undefined,
              communityId: undefined,
            }))
          }
        >
          <SelectTrigger id="settlement-search-area">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Усі області</SelectItem>
            {areas.map((area) => (
              <SelectItem key={area.id} value={area.id}>
                {area.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="form-field">
        <Label htmlFor="settlement-search-region">Район</Label>
        <Select
          value={filters.regionId ?? ALL}
          onValueChange={(value) =>
            setFilters((current) => ({
              ...current,
              regionId: value === ALL ? undefined : value,
              communityId: undefined,
            }))
          }
        >
          <SelectTrigger id="settlement-search-region">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Усі райони</SelectItem>
            {regions.map((region) => (
              <SelectItem key={region.id} value={region.id}>
                {region.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="form-field">
        <Label htmlFor="settlement-search-community">Громада</Label>
        <Select
          value={filters.communityId ?? ALL}
          onValueChange={(value) =>
            setFilters((current) => ({
              ...current,
              communityId: value === ALL ? undefined : value,
            }))
          }
        >
          <SelectTrigger id="settlement-search-community">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Усі громади</SelectItem>
            {communities.map((community) => (
              <SelectItem key={community.id} value={community.id}>
                {community.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {state.status === "searching" && <p role="status">Шукаємо…</p>}
      {state.status === "error" && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === "results" && (
        <ul className="m-0 flex list-none flex-col gap-[0.4rem] p-0">
          {state.results.length === 0 && <li className="lede">Нічого не знайдено.</li>}
          {state.results.map((suggestion) => (
            <li key={suggestion.settlement_id}>
              <Button
                variant="secondary"
                type="button"
                onClick={() => onSelect(suggestion)}
              >
                {suggestion.title} ({suggestion.category}) — {suggestion.community_name}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
