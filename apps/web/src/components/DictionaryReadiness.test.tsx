import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DictionaryResponse } from "../api";
import { DictionaryReadiness } from "./DictionaryReadiness";

function baseDictionary(
  overrides: Partial<DictionaryResponse> = {},
): DictionaryResponse {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    status: "draft",
    title: "Словник",
    description: null,
    article_description: null,
    dictionary_type: null,
    publisher: null,
    publication_year: null,
    edition: null,
    isbn: null,
    digital_source: null,
    legal_status: "public_domain",
    license_type: null,
    permission_reference: null,
    rights_note: null,
    contributors: [],
    language_codes: ["uk"],
    created_at: "2026-08-15T12:00:00Z",
    updated_at: "2026-08-15T12:00:00Z",
    missing_required_fields: [],
    readiness_blockers: [],
    source: null,
    ...overrides,
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("DictionaryReadiness", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the draft badge and lists every readiness blocker", () => {
    render(
      <DictionaryReadiness
        dictionary={baseDictionary({
          readiness_blockers: [
            { code: "languages", message: "Вкажіть щонайменше одну мову." },
            { code: "source_missing", message: "Завантажте файл словника (PDF)." },
          ],
        })}
        onConfigured={vi.fn()}
        onScanned={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Чернетка");
    expect(screen.getByText("Вкажіть щонайменше одну мову.")).toBeInTheDocument();
    expect(
      screen.getByText("Завантажте файл словника (PDF)."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Позначити як готовий до обробки" }),
    ).toBeDisabled();
  });

  it("enables confirmation once every blocker is resolved and reports success", async () => {
    const configured = baseDictionary({ status: "configured" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, configured)));
    const onConfigured = vi.fn();

    render(
      <DictionaryReadiness
        dictionary={baseDictionary()}
        onConfigured={onConfigured}
        onScanned={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", {
      name: "Позначити як готовий до обробки",
    });
    expect(button).toBeEnabled();
    fireEvent.click(button);

    await waitFor(() => expect(onConfigured).toHaveBeenCalledWith(configured));
  });

  it("shows an error and keeps the draft status when confirmation is rejected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(422, {
          blockers: [{ code: "title", message: "Вкажіть назву словника." }],
        }),
      ),
    );

    render(
      <DictionaryReadiness
        dictionary={baseDictionary()}
        onConfigured={vi.fn()}
        onScanned={vi.fn()}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Позначити як готовий до обробки" }),
    );

    expect(
      await screen.findByText("Не вдалося підтвердити готовність. Спробуйте ще раз."),
    ).toBeInTheDocument();
  });

  it("hides the confirmation button once the dictionary is configured", () => {
    render(
      <DictionaryReadiness
        dictionary={baseDictionary({ status: "configured" })}
        onConfigured={vi.fn()}
        onScanned={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Готовий до обробки");
    expect(
      screen.queryByRole("button", { name: "Позначити як готовий до обробки" }),
    ).not.toBeInTheDocument();
  });

  it("shows a finish-scanning button once configured and reports success (BH-58)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, { id: "11111111-1111-1111-1111-111111111111", status: "scanned" }),
      ),
    );
    const onScanned = vi.fn();

    render(
      <DictionaryReadiness
        dictionary={baseDictionary({ status: "configured" })}
        onConfigured={vi.fn()}
        onScanned={onScanned}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Завершити сканування" }));

    await waitFor(() =>
      expect(onScanned).toHaveBeenCalledWith(
        expect.objectContaining({ status: "scanned" }),
      ),
    );
  });

  it("shows the server's error when finishing scanning without lexemes (BH-58)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(422, {
          code: "no_lexemes",
          message: "Словник ще не має жодної виділеної лексеми.",
        }),
      ),
    );

    render(
      <DictionaryReadiness
        dictionary={baseDictionary({ status: "configured" })}
        onConfigured={vi.fn()}
        onScanned={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Завершити сканування" }));

    expect(
      await screen.findByText("Словник ще не має жодної виділеної лексеми."),
    ).toBeInTheDocument();
  });

  it("hides both transition buttons once scanning is finished (BH-58)", () => {
    render(
      <DictionaryReadiness
        dictionary={baseDictionary({ status: "scanned" })}
        onConfigured={vi.fn()}
        onScanned={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Скановано");
    expect(
      screen.queryByRole("button", { name: "Завершити сканування" }),
    ).not.toBeInTheDocument();
  });

  it("offers no action while the dictionary is auto-advancing", () => {
    render(
      <DictionaryReadiness
        dictionary={baseDictionary({ status: "in_progress" })}
        onConfigured={vi.fn()}
        onScanned={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("В опрацюванні");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("publishes a processed dictionary and reports the new status", async () => {
    const published = baseDictionary({ status: "published" });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, { id: published.id, status: "published" }),
      ),
    );
    const onPublished = vi.fn();

    render(
      <DictionaryReadiness
        dictionary={baseDictionary({ status: "processed" })}
        onConfigured={vi.fn()}
        onScanned={vi.fn()}
        onPublished={onPublished}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Опублікувати словник" }),
    );

    await waitFor(() =>
      expect(onPublished).toHaveBeenCalledWith(
        expect.objectContaining({ status: "published" }),
      ),
    );
  });
});
