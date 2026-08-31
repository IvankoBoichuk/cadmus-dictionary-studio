import { useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { abbreviationsExportUrl, type AbbreviationResponse } from "../api";
import { AbbreviationForm } from "../components/AbbreviationForm";
import { AbbreviationImportPanel } from "../components/AbbreviationImportPanel";
import { AbbreviationsTable } from "../components/AbbreviationsTable";
import { useAbbreviations } from "../hooks/useAbbreviations";

function AbbreviationsWorkspace({ dictionaryId }: { dictionaryId: string }) {
  const { state, deleteState, remove, upsert, mergeImported } =
    useAbbreviations(dictionaryId);
  const [editing, setEditing] = useState<AbbreviationResponse | null>(null);

  const handleDelete = (item: AbbreviationResponse) => {
    if (window.confirm(`Видалити скорочення «${item.abbreviation}»?`)) {
      void remove(item.id);
    }
  };

  const handleSaved = (saved: AbbreviationResponse) => {
    upsert(saved);
    setEditing(null);
  };

  return (
    <>
      <div className="form-section" aria-labelledby="export-heading">
        <h2 id="export-heading">Експорт конфігурації</h2>
        <p className="section-hint">
          Завантажте поточний список скорочень у машинозчитуваному форматі для
          повторного використання.
        </p>
        <div className="form-actions">
          <a
            className="ml-4 inline-block font-[650] text-primary hover:underline"
            href={abbreviationsExportUrl(dictionaryId, "json")}
          >
            Експортувати JSON
          </a>
          <a
            className="ml-4 inline-block font-[650] text-primary hover:underline"
            href={abbreviationsExportUrl(dictionaryId, "csv")}
          >
            Експортувати CSV
          </a>
        </div>
      </div>

      {state.status === "loading" && <p role="status">Завантажуємо скорочення…</p>}
      {state.status === "error" && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === "loaded" && (
        <div className="form-section">
          <h2>Список скорочень</h2>
          <AbbreviationsTable
            abbreviations={state.abbreviations}
            onEdit={setEditing}
            onDelete={handleDelete}
            deleteState={deleteState}
          />
        </div>
      )}

      <AbbreviationForm
        dictionaryId={dictionaryId}
        editing={editing}
        onSaved={handleSaved}
        onCancel={() => setEditing(null)}
      />

      <AbbreviationImportPanel dictionaryId={dictionaryId} onImported={mergeImported} />
    </>
  );
}

export function AbbreviationsPage() {
  const { dictionaryId } = useParams<{ dictionaryId: string }>();

  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return (
    <>
      <h2 className="mb-2 text-[1.15rem]">Скорочення словника</h2>
      <p className="max-w-[60ch] text-[0.9rem] text-muted-foreground">
        Налаштуйте структурований список скорочень, який Cadmus
        використовуватиме під час виділення полів статей.
      </p>
      <div className="dictionary-form">
        <AbbreviationsWorkspace dictionaryId={dictionaryId} />
      </div>
    </>
  );
}
