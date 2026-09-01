import ReactMarkdown from "react-markdown";

import type { EntryRenderState } from "../hooks/useEntryRender";

/**
 * Read-only preview of the entry composed through its schema's presentation
 * formula (BH-148). Never an error state on its own — a missing formula or a
 * broken template renders as a hint.
 */
export function EntryRenderPanel({ state }: { state: EntryRenderState }) {
  return (
    <section
      className="form-section"
      aria-labelledby="entry-render-heading"
    >
      <h3 id="entry-render-heading" className="m-0 text-[0.95rem]">
        Перегляд статті
      </h3>
      {state.status === "loading" && (
        <p className="m-0 text-[0.85rem] text-muted-foreground" role="status">
          Будуємо перегляд…
        </p>
      )}
      {state.status === "error" && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === "loaded" && state.markdown !== null && (
        <div className="prose prose-sm max-w-none text-[0.9rem]">
          <ReactMarkdown skipHtml>{state.markdown}</ReactMarkdown>
        </div>
      )}
      {state.status === "loaded" &&
        state.markdown === null &&
        state.reason === "template_error" && (
          <p className="form-error" role="alert">
            Помилка у формулі подання: {state.error}
          </p>
        )}
      {state.status === "loaded" &&
        state.markdown === null &&
        state.reason !== "template_error" && (
          <p className="m-0 text-[0.85rem] text-muted-foreground">
            {state.reason === "no_formula"
              ? "Для схеми цієї статті не задано формулу подання."
              : "Для статті ще не активовано схему."}
          </p>
        )}
    </section>
  );
}
