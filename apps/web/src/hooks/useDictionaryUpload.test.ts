import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MAX_CLIENT_UPLOAD_SIZE_BYTES, useDictionaryUpload } from "./useDictionaryUpload";

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
  aborted = false;
  sentFormData: FormData | null = null;

  constructor() {
    FakeXhr.instances.push(this);
  }

  open(): void {}

  send(body: FormData): void {
    this.sentFormData = body;
  }

  abort(): void {
    this.aborted = true;
    this.onabort?.();
  }

  respond(status: number, payload: unknown): void {
    this.status = status;
    this.responseText = JSON.stringify(payload);
    this.onload?.();
  }

  progress(loaded: number, total: number): void {
    this.upload.onprogress?.({
      lengthComputable: true,
      loaded,
      total,
    } as ProgressEvent);
  }
}

function pdfFile(name = "dictionary.pdf", size = 1024): File {
  const content = new Uint8Array(size);
  return new File([content], name, { type: "application/pdf" });
}

describe("useDictionaryUpload", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    FakeXhr.instances = [];
  });

  it("rejects a non-PDF extension before ever contacting the server", () => {
    const { result } = renderHook(() => useDictionaryUpload());

    act(() => result.current.selectFile(pdfFile("notes.txt")));

    expect(result.current.state).toEqual({
      status: "error",
      file: expect.any(File),
      message: expect.stringContaining(".pdf"),
    });
  });

  it("rejects a file over the client-side size guard", () => {
    const { result } = renderHook(() => useDictionaryUpload());
    const oversized = pdfFile("big.pdf", MAX_CLIENT_UPLOAD_SIZE_BYTES + 1);

    act(() => result.current.selectFile(oversized));

    expect(result.current.state.status).toBe("error");
  });

  it("accepts a valid PDF and shows it as selected before upload", () => {
    const { result } = renderHook(() => useDictionaryUpload());
    const file = pdfFile();

    act(() => result.current.selectFile(file));

    expect(result.current.state).toEqual({ status: "selected", file });
  });

  it("tracks upload progress and transitions to done on success", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { result } = renderHook(() => useDictionaryUpload());
    act(() => result.current.selectFile(pdfFile()));

    act(() => {
      void result.current.upload(pdfFile());
    });
    await waitFor(() => expect(result.current.state.status).toBe("uploading"));

    const xhr = FakeXhr.instances.at(-1);
    expect(xhr).toBeDefined();
    act(() => xhr?.progress(50, 100));
    await waitFor(() => {
      expect(result.current.state).toMatchObject({
        status: "uploading",
        progress: 0.5,
      });
    });

    const dictionary = {
      id: "11111111-1111-1111-1111-111111111111",
      status: "draft",
      missing_required_fields: ["title", "languages", "legal_status"],
    };
    act(() => xhr?.respond(202, dictionary));

    await waitFor(() =>
      expect(result.current.state).toMatchObject({ status: "done", dictionary }),
    );
  });

  it("surfaces a duplicate-source response without a generic error message", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { result } = renderHook(() => useDictionaryUpload());

    act(() => {
      void result.current.upload(pdfFile());
    });
    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    const duplicate = {
      code: "duplicate_source",
      dictionary_id: "22222222-2222-2222-2222-222222222222",
      title: "Наявний словник",
      message: "Такий файл уже завантажено раніше.",
    };
    act(() => FakeXhr.instances[0]?.respond(409, duplicate));

    await waitFor(() =>
      expect(result.current.state).toMatchObject({ status: "duplicate", duplicate }),
    );
  });

  it("ignores a second upload call while one is already in flight", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const { result } = renderHook(() => useDictionaryUpload());

    act(() => {
      void result.current.upload(pdfFile());
      void result.current.upload(pdfFile());
    });

    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
  });
});
