import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EntryReferenceLinkResponse, ReferenceLemmaResponse } from "../api";
import { EntryReferenceLinksSection } from "./EntryReferenceLinksSection";

const ENTRY_ID = "33333333-3333-3333-3333-333333333333";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function lemma(overrides: Partial<ReferenceLemmaResponse> = {}): ReferenceLemmaResponse {
  return {
    id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    lemma: "хата",
    normalized_lemma: "хата",
    part_of_speech: "noun",
    key_tags: [],
    is_standard: true,
    ...overrides,
  };
}

function link(
  overrides: Partial<EntryReferenceLinkResponse> = {},
): EntryReferenceLinkResponse {
  return {
    id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    entry_id: ENTRY_ID,
    reference_lemma_id: lemma().id,
    relation_type: "standard_equivalent",
    origin: "manual",
    validation_status: "confirmed",
    confidence: null,
    created_at: "2026-08-20T10:00:00Z",
    lemma: lemma(),
    ...overrides,
  };
}

function renderSection() {
  return render(
    <MemoryRouter>
      <EntryReferenceLinksSection entryId={ENTRY_ID} />
    </MemoryRouter>,
  );
}

describe("EntryReferenceLinksSection", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists a confirmed link with its relation type", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [link()])));

    renderSection();

    expect(await screen.findByText("хата")).toBeInTheDocument();
    expect(screen.getByText("Літературний відповідник")).toBeInTheDocument();
  });

  it("shows an empty state when there are no links", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [])));

    renderSection();

    expect(
      await screen.findByText(/Знайдіть лему у VESUM/),
    ).toBeInTheDocument();
  });

  it("searches VESUM and confirms a picked lemma as a link", async () => {
    const created = link({ relation_type: "synonym" });
    const fetchMock = vi.fn((input: unknown, init?: RequestInit) => {
      const url = String(input);
      if ((init?.method ?? "GET") === "GET" && url.endsWith("/reference-links")) {
        return Promise.resolve(jsonResponse(200, []));
      }
      if (url.includes("/lemmas?")) {
        return Promise.resolve(jsonResponse(200, [lemma()]));
      }
      if (init?.method === "POST") {
        return Promise.resolve(jsonResponse(201, created));
      }
      return Promise.resolve(jsonResponse(200, []));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSection();
    await screen.findByText(/Знайдіть лему у VESUM/);

    fireEvent.click(screen.getByRole("button", { name: "Додати відповідник" }));
    fireEvent.change(screen.getByLabelText("Тип зв'язку"), {
      target: { value: "synonym" },
    });
    fireEvent.change(
      await screen.findByLabelText("Пошук леми або словоформи"),
      { target: { value: "хат" } },
    );

    fireEvent.click(await screen.findByRole("button", { name: "Прив'язати" }));

    await waitFor(() =>
      expect(screen.getByText("Синонім")).toBeInTheDocument(),
    );
    const postCall = fetchMock.mock.calls.find(
      ([, init]) => (init as RequestInit | undefined)?.method === "POST",
    );
    expect(JSON.parse((postCall![1] as RequestInit).body as string)).toEqual({
      reference_lemma_id: lemma().id,
      relation_type: "synonym",
    });
  });

  it("surfaces the API message when a non-standard lemma is rejected", async () => {
    const fetchMock = vi.fn((input: unknown, init?: RequestInit) => {
      const url = String(input);
      if ((init?.method ?? "GET") === "GET" && url.endsWith("/reference-links")) {
        return Promise.resolve(jsonResponse(200, []));
      }
      if (url.includes("/lemmas?")) {
        return Promise.resolve(
          jsonResponse(200, [lemma({ is_standard: false })]),
        );
      }
      if (init?.method === "POST") {
        return Promise.resolve(
          jsonResponse(422, {
            code: "non_standard_reference",
            message: "Для літературного відповідника виберіть нормативну лему.",
          }),
        );
      }
      return Promise.resolve(jsonResponse(200, []));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSection();
    await screen.findByText(/Знайдіть лему у VESUM/);

    fireEvent.click(screen.getByRole("button", { name: "Додати відповідник" }));
    fireEvent.change(
      await screen.findByLabelText("Пошук леми або словоформи"),
      { target: { value: "хат" } },
    );
    fireEvent.click(await screen.findByRole("button", { name: "Прив'язати" }));

    expect(
      await screen.findByText(
        "Для літературного відповідника виберіть нормативну лему.",
      ),
    ).toBeInTheDocument();
  });

  it("removes a link after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = vi.fn((_input: unknown, init?: RequestInit) => {
      if (init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return Promise.resolve(jsonResponse(200, [link()]));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSection();
    await screen.findByText("хата");

    fireEvent.click(screen.getByRole("button", { name: "Вилучити прив'язку" }));

    await waitFor(() =>
      expect(screen.getByText(/Знайдіть лему у VESUM/)).toBeInTheDocument(),
    );
  });
});
