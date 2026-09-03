import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  SettlementImportCommitResponse,
  SettlementImportPreviewResponse,
} from "../api";
import { useSettlementImport } from "./useSettlementImport";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

class FakeXhr {
  static instances: FakeXhr[] = [];

  status = 0;
  responseText = "";
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = {
    onprogress: null,
  };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;

  constructor() {
    FakeXhr.instances.push(this);
  }

  open(): void {}

  send(): void {}

  abort(): void {
    this.onabort?.();
  }

  respond(status: number, payload: unknown): void {
    this.status = status;
    this.responseText = JSON.stringify(payload);
    this.onload?.();
  }
}

function csvFile(): File {
  return new File(["source_label\n"], "settlements.csv", { type: "text/csv" });
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("useSettlementImport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    FakeXhr.instances = [];
  });

  it("previews a file and reports valid/invalid rows", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { result } = renderHook(() => useSettlementImport(DICTIONARY_ID, vi.fn()));

    act(() => {
      void result.current.preview(csvFile());
    });
    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));

    const previewResponse: SettlementImportPreviewResponse = {
      rows: [
        {
          row_number: 1,
          valid: true,
          input: {
            source_label: "Іванівка",
            source_note: null,
            district: null,
            modern_settlement_name: null,
            settlement_category: null,
            settlement_id: null,
          },
          errors: {},
          duplicate_of: null,
        },
      ],
      valid_count: 1,
      error_count: 0,
    };
    act(() => FakeXhr.instances[0]?.respond(200, previewResponse));

    await waitFor(() =>
      expect(result.current.state).toMatchObject({
        status: "previewed",
        preview: previewResponse,
      }),
    );
  });

  it("surfaces an unparsable-file error", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { result } = renderHook(() => useSettlementImport(DICTIONARY_ID, vi.fn()));

    act(() => {
      void result.current.preview(csvFile());
    });
    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    act(() =>
      FakeXhr.instances[0]?.respond(422, {
        code: "unparsable_import_file",
        message: "Файл не вдалося розібрати: bad input",
      }),
    );

    await waitFor(() =>
      expect(result.current.state).toMatchObject({
        status: "error",
        message: "Файл не вдалося розібрати: bad input",
      }),
    );
  });

  it("commits only the valid rows and reports the outcome", async () => {
    const outcome: SettlementImportCommitResponse = {
      imported: [
        {
          id: "22222222-2222-2222-2222-222222222222",
          source_label: "Іванівка",
          status: "unresolved",
          source_note: null,
          district: null,
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
        },
      ],
      skipped: [{ row_number: 2, errors: { source_label: "Дублікат." } }],
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, outcome));
    vi.stubGlobal("fetch", fetchMock);
    const onImported = vi.fn();
    const { result } = renderHook(() =>
      useSettlementImport(DICTIONARY_ID, onImported),
    );

    const preview: SettlementImportPreviewResponse = {
      rows: [
        {
          row_number: 1,
          valid: true,
          input: {
            source_label: "Іванівка",
            source_note: null,
            district: null,
            modern_settlement_name: null,
            settlement_category: null,
            settlement_id: null,
          },
          errors: {},
          duplicate_of: null,
        },
        {
          row_number: 2,
          valid: false,
          input: null,
          errors: { source_label: "Дублікат." },
          duplicate_of: null,
        },
      ],
      valid_count: 1,
      error_count: 1,
    };

    act(() => {
      void result.current.commit(preview);
    });

    await waitFor(() =>
      expect(result.current.state).toMatchObject({ status: "done", outcome }),
    );
    expect(onImported).toHaveBeenCalledWith(outcome.imported);
    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(requestInit.body as string) as { rows: unknown[] };
    expect(body.rows).toHaveLength(1);
  });

  it("resets back to idle", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { result } = renderHook(() => useSettlementImport(DICTIONARY_ID, vi.fn()));
    act(() => {
      void result.current.preview(csvFile());
    });
    await waitFor(() => expect(result.current.state.status).toBe("previewing"));

    act(() => result.current.reset());

    expect(result.current.state).toEqual({ status: "idle" });
  });
});
