import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SettlementMappingResponse } from "../api";
import { SettlementForm } from "./SettlementForm";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function existing(
  overrides: Partial<SettlementMappingResponse> = {},
): SettlementMappingResponse {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    source_label: "Іванівка",
    status: "unresolved",
    source_note: null,
    modern_settlement_name: null,
    settlement_category: null,
    area_id: null,
    region_id: null,
    community_id: null,
    settlement_id: null,
    community_geometry_id: null,
    area_name: null,
    region_name: null,
    community_name: null,
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

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Routes every geography lookup made by the embedded search combobox to `[]`. */
function stubEmptyGeographyLookups(): ReturnType<typeof vi.fn> {
  return vi.fn().mockImplementation((url: string) => {
    if (url.includes("/geography/")) return Promise.resolve(jsonResponse(200, []));
    return Promise.resolve(jsonResponse(200, []));
  });
}

describe("SettlementForm", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requires a source label (BH-48)", async () => {
    vi.stubGlobal("fetch", stubEmptyGeographyLookups());
    render(
      <SettlementForm dictionaryId={DICTIONARY_ID} editing={null} onSaved={vi.fn()} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Додати" }));

    await waitFor(() =>
      expect(
        screen.getByText("Вкажіть географічну позначку з оригіналу."),
      ).toBeInTheDocument(),
    );
  });

  it("saves a new mapping with just a source label", async () => {
    const created = existing();
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/geography/")) return Promise.resolve(jsonResponse(200, []));
      if (url.includes("/settlements") && url.includes("query="))
        return Promise.resolve(jsonResponse(200, []));
      return Promise.resolve(jsonResponse(201, created));
    });
    vi.stubGlobal("fetch", fetchMock);
    const onSaved = vi.fn();

    render(
      <SettlementForm dictionaryId={DICTIONARY_ID} editing={null} onSaved={onSaved} />,
    );
    fireEvent.change(screen.getByLabelText("Позначка з оригіналу"), {
      target: { value: "Іванівка" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Додати" }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(created));
  });

  it("never renders a control that submits status=confirmed (AC9)", () => {
    vi.stubGlobal("fetch", stubEmptyGeographyLookups());
    render(
      <SettlementForm dictionaryId={DICTIONARY_ID} editing={null} onSaved={vi.fn()} />,
    );

    expect(screen.queryByText(/підтвердж/i)).not.toBeInTheDocument();
  });

  it("picking a search suggestion fills the modern fields and can be cleared (AC8, AC9)", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/geography/")) return Promise.resolve(jsonResponse(200, []));
      if (url.includes("/search?"))
        return Promise.resolve(
          jsonResponse(200, [
            {
              settlement_id: "33333333-3333-3333-3333-333333333333",
              title: "Іванівка",
              category: "село",
              community_id: "44444444-4444-4444-4444-444444444444",
              community_name: "Львівська громада",
              region_id: "55555555-5555-5555-5555-555555555555",
              area_id: "66666666-6666-6666-6666-666666666666",
            },
          ]),
        );
      return Promise.resolve(jsonResponse(200, []));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <SettlementForm dictionaryId={DICTIONARY_ID} editing={null} onSaved={vi.fn()} />,
    );

    fireEvent.change(screen.getByLabelText("Пошук населеного пункту"), {
      target: { value: "Іван" },
    });

    const suggestionButton = await screen.findByRole(
      "button",
      { name: /Іванівка \(село\)/ },
      { timeout: 1000 },
    );
    fireEvent.click(suggestionButton);

    await waitFor(() =>
      expect(screen.getByText(/Зіставлено з: Іванівка/)).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Скасувати зіставлення" }));

    expect(screen.getByLabelText("Пошук населеного пункту")).toBeInTheDocument();
  });
});
