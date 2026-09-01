import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SettlementMappingResponse } from "../api";
import { SettlementsTable } from "./SettlementsTable";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function row(
  overrides: Partial<SettlementMappingResponse> = {},
): SettlementMappingResponse {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    source_label: "Іванівка",
    status: "suggested",
    source_note: null,
    modern_settlement_name: "Іванівка",
    settlement_category: "село",
    area_id: null,
    region_id: null,
    community_id: null,
    settlement_id: null,
    community_geometry_id: null,
    area_name: null,
    region_name: null,
    community_name: "Львівська громада",
    external_community_id: null,
    katottg: null,
    koatuu: null,
    confirmed_by: null,
    confirmed_at: null,
    created_at: "2026-08-16T12:00:00Z",
    updated_at: "2026-08-16T12:00:00Z",
    ...overrides,
  };
}

function renderTable(items: SettlementMappingResponse[]) {
  return render(
    <SettlementsTable
      dictionaryId={DICTIONARY_ID}
      mappings={items}
      onSaved={vi.fn()}
      onDelete={vi.fn()}
      onConfirm={vi.fn()}
      onUnconfirm={vi.fn()}
      deleteState={{}}
    />,
  );
}

describe("SettlementsTable", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reveals the inline add-row form when the + button is clicked", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [])));
    renderTable([]);

    fireEvent.click(
      screen.getByRole("button", { name: "Додати географічну мітку" }),
    );

    expect(screen.getByLabelText("Позначка з оригіналу")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Зберегти" })).toBeInTheDocument();
  });

  it("swaps a data row for the inline form when the edit action is used", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [])));
    renderTable([row()]);

    fireEvent.click(screen.getByRole("button", { name: "Редагувати" }));

    expect(screen.getByLabelText("Позначка з оригіналу")).toHaveValue("Іванівка");
  });

  it("shows Підтвердити for a suggested mapping and calls back", () => {
    const onConfirm = vi.fn();
    render(
      <SettlementsTable
        dictionaryId={DICTIONARY_ID}
        mappings={[row({ status: "suggested" })]}
        onSaved={vi.fn()}
        onDelete={vi.fn()}
        onConfirm={onConfirm}
        onUnconfirm={vi.fn()}
        deleteState={{}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Підтвердити" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
