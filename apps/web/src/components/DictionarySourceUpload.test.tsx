import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DictionarySourceUpload } from "./DictionarySourceUpload";

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

function pdfFile(name = "dictionary.pdf", size = 2048): File {
  return new File([new Uint8Array(size)], name, { type: "application/pdf" });
}

describe("DictionarySourceUpload", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    FakeXhr.instances = [];
  });

  it("shows the selected file's name and size before uploading", () => {
    render(<DictionarySourceUpload onUploaded={vi.fn()} />);

    const input = screen.getByLabelText("PDF-файл");
    fireEvent.change(input, { target: { files: [pdfFile("Словник.pdf", 4096)] } });

    expect(screen.getByText(/Словник\.pdf/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Завантажити файл" })).toBeInTheDocument();
  });

  it("shows a client-side validation error for a non-PDF file", () => {
    render(<DictionarySourceUpload onUploaded={vi.fn()} />);

    const input = screen.getByLabelText("PDF-файл");
    fireEvent.change(input, {
      target: { files: [new File(["hi"], "notes.txt", { type: "text/plain" })] },
    });

    expect(screen.getByRole("alert")).toHaveTextContent(".pdf");
  });

  it("uploads the file and calls onUploaded once the server responds", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    const onUploaded = vi.fn();
    render(<DictionarySourceUpload onUploaded={onUploaded} />);

    fireEvent.change(screen.getByLabelText("PDF-файл"), {
      target: { files: [pdfFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Завантажити файл" }));

    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    const dictionary = {
      id: "11111111-1111-1111-1111-111111111111",
      status: "draft",
      missing_required_fields: [],
    };
    FakeXhr.instances[0]?.respond(202, dictionary);

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith(dictionary));
  });

  it("lets the user retry after a failed upload", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    render(<DictionarySourceUpload onUploaded={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("PDF-файл"), {
      target: { files: [pdfFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Завантажити файл" }));

    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    FakeXhr.instances[0]?.respond(422, { errors: { file: "Невірна сигнатура." } });

    const retryButton = await screen.findByRole("button", { name: "Спробувати ще раз" });
    fireEvent.click(retryButton);

    expect(
      screen.getByRole("button", { name: "Завантажити файл" }),
    ).toBeInTheDocument();
  });
});
