import { Download, Upload } from "lucide-react";
import { Navigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

import { settlementsExportUrl, type SettlementMappingResponse } from "../api";
import { SettlementImportPanel } from "../components/SettlementImportPanel";
import { SettlementsTable } from "../components/SettlementsTable";
import { useSettlements } from "../hooks/useSettlements";

function SettlementsWorkspace({ dictionaryId }: { dictionaryId: string }) {
  const {
    state,
    deleteState,
    remove,
    upsert,
    mergeImported,
    confirm,
    unconfirm,
  } = useSettlements(dictionaryId);

  const handleDelete = (item: SettlementMappingResponse) => {
    if (window.confirm(`Видалити географічну мітку «${item.source_label}»?`)) {
      void remove(item.id);
    }
  };

  return (
    <>
      <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="mb-2 text-[1.15rem]">Географічні мітки словника</h2>
          <p className="max-w-[60ch] text-[0.9rem] text-muted-foreground">
            Зіставте географічні позначки з оригіналу словника із сучасними
            населеними пунктами, зберігаючи історичну форму та адміністративну
            належність.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="secondary" size="sm" type="button">
                <Upload aria-hidden="true" />
                Імпорт
              </Button>
            </PopoverTrigger>
            <PopoverContent className="max-h-[70vh] w-[min(90vw,32rem)] overflow-y-auto">
              <SettlementImportPanel
                dictionaryId={dictionaryId}
                onImported={mergeImported}
              />
            </PopoverContent>
          </Popover>

          <Popover>
            <PopoverTrigger asChild>
              <Button variant="secondary" size="sm" type="button">
                <Download aria-hidden="true" />
                Експорт
              </Button>
            </PopoverTrigger>
            <PopoverContent className="grid gap-1">
              <p className="m-0 mb-1 text-[0.8rem] text-muted-foreground">
                Завантажте поточний список у машинозчитуваному форматі.
              </p>
              <a
                className="rounded-md px-2 py-1.5 font-[650] text-primary no-underline hover:bg-accent"
                href={settlementsExportUrl(dictionaryId, "json")}
              >
                Експортувати JSON
              </a>
              <a
                className="rounded-md px-2 py-1.5 font-[650] text-primary no-underline hover:bg-accent"
                href={settlementsExportUrl(dictionaryId, "csv")}
              >
                Експортувати CSV
              </a>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      <div className="dictionary-form">
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
              dictionaryId={dictionaryId}
              mappings={state.mappings}
              onSaved={upsert}
              onDelete={handleDelete}
              onConfirm={(item) => void confirm(item.id)}
              onUnconfirm={(item) => void unconfirm(item.id)}
              deleteState={deleteState}
            />
          </div>
        )}
      </div>
    </>
  );
}

export function SettlementsPage() {
  const { dictionaryId } = useParams<{ dictionaryId: string }>();

  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return <SettlementsWorkspace dictionaryId={dictionaryId} />;
}
