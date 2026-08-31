import { useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { settlementsExportUrl, type SettlementMappingResponse } from "../api";
import { SettlementForm } from "../components/SettlementForm";
import { SettlementImportPanel } from "../components/SettlementImportPanel";
import { SettlementsTable } from "../components/SettlementsTable";
import { useSettlements } from "../hooks/useSettlements";

function SettlementsWorkspace({ dictionaryId }: { dictionaryId: string }) {
  const { state, deleteState, remove, upsert, mergeImported, confirm, unconfirm } =
    useSettlements(dictionaryId);
  const [editing, setEditing] = useState<SettlementMappingResponse | null>(null);

  const handleDelete = (item: SettlementMappingResponse) => {
    if (window.confirm(`Видалити географічну мітку «${item.source_label}»?`)) {
      void remove(item.id);
    }
  };

  const handleSaved = (saved: SettlementMappingResponse) => {
    upsert(saved);
    setEditing(null);
  };

  return (
    <>
      <div className="form-section" aria-labelledby="settlement-export-heading">
        <h2 id="settlement-export-heading">Експорт конфігурації</h2>
        <p className="section-hint">
          Завантажте поточний список географічних міток у машинозчитуваному
          форматі для повторного використання.
        </p>
        <div className="form-actions">
          <a
            className="ml-4 inline-block font-[650] text-primary hover:underline"
            href={settlementsExportUrl(dictionaryId, "json")}
          >
            Експортувати JSON
          </a>
          <a
            className="ml-4 inline-block font-[650] text-primary hover:underline"
            href={settlementsExportUrl(dictionaryId, "csv")}
          >
            Експортувати CSV
          </a>
        </div>
      </div>

      {state.status === "loading" && (
        <p role="status">Завантажуємо географічні мітки…</p>
      )}
      {state.status === "error" && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === "loaded" && (
        <div className="form-section">
          <h2>Список географічних міток</h2>
          <SettlementsTable
            mappings={state.mappings}
            onEdit={setEditing}
            onDelete={handleDelete}
            onConfirm={(item) => void confirm(item.id)}
            onUnconfirm={(item) => void unconfirm(item.id)}
            deleteState={deleteState}
          />
        </div>
      )}

      <SettlementForm
        dictionaryId={dictionaryId}
        editing={editing}
        onSaved={handleSaved}
        onCancel={() => setEditing(null)}
      />

      <SettlementImportPanel dictionaryId={dictionaryId} onImported={mergeImported} />
    </>
  );
}

export function SettlementsPage() {
  const { dictionaryId } = useParams<{ dictionaryId: string }>();

  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return (
    <>
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Словник</p>
        <h1 id="page-title">Географічні мітки словника</h1>
        <p className="lede">
          Зіставте географічні позначки з оригіналу словника із сучасними
          населеними пунктами, зберігаючи історичну форму та адміністративну
          належність.
        </p>
      </section>
      <div className="dictionary-form">
        <SettlementsWorkspace dictionaryId={dictionaryId} />
      </div>
    </>
  );
}
