import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SettlementMappingResponse } from "../api";
import { DistrictByCommunityPanel } from "./DistrictByCommunityPanel";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";
const COMMUNITY_ID = "33333333-3333-3333-3333-333333333333";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mapping(
  overrides: Partial<SettlementMappingResponse> = {},
): SettlementMappingResponse {
  return {
    id: crypto.randomUUID(),
    source_label: "Атаки",
    status: "confirmed",
    source_note: null,
    district: null,
    modern_settlement_name: "Атаки",
    settlement_category: "село",
    area_id: null,
    region_id: null,
    community_id: COMMUNITY_ID,
    settlement_id: null,
    community_geometry_id: null,
    area_name: null,
    region_name: null,
    community_name: "Хотинська територіальна громада",
    external_community_id: null,
    katottg: null,
    koatuu: null,
    confirmed_by: null,
    confirmed_at: null,
    created_at: "2026-09-01T12:00:00Z",
    updated_at: "2026-09-01T12:00:00Z",
    ...overrides,
  };
}

describe("DistrictByCommunityPanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders nothing when no mapping has a community", () => {
    const { container } = render(
      <DistrictByCommunityPanel
        dictionaryId={DICTIONARY_ID}
        mappings={[mapping({ community_id: null })]}
        onApplied={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("posts the bulk district and reports the count", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { updated: 5 }));
    vi.stubGlobal("fetch", fetchMock);
    const onApplied = vi.fn();

    render(
      <DistrictByCommunityPanel
        dictionaryId={DICTIONARY_ID}
        mappings={[mapping(), mapping()]}
        onApplied={onApplied}
      />,
    );

    fireEvent.click(screen.getByLabelText("Громада"));
    fireEvent.click(
      screen.getByRole("option", { name: "Хотинська територіальна громада" }),
    );
    fireEvent.change(screen.getByLabelText("Скорочення району"), {
      target: { value: "Хот." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Застосувати" }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Оновлено записів: 5"),
    );
    expect(onApplied).toHaveBeenCalled();
    const body = JSON.parse(
      (fetchMock.mock.calls[0]![1] as RequestInit).body as string,
    );
    expect(body).toEqual({ community_id: COMMUNITY_ID, district: "Хот." });
  });
});
