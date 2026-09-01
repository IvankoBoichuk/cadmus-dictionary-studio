import { Plus } from "lucide-react";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import type { ReferenceLemmaResponse } from "../api";
import { useReferenceLemmaSearch } from "../hooks/useReferenceLemmaSearch";
import { ReferenceLemmaCard } from "./ReferenceLemmaCard";

/**
 * Debounced search over a reference lexicon. Pure browsing when `onSelect`
 * is omitted; when provided, every result gets an add button so the entry
 * page can turn a hit into a confirmed link.
 */
export function ReferenceLemmaSearchCombobox({
  code,
  onSelect,
  selectLabel = "Прив'язати",
}: {
  code: string;
  onSelect?: (lemma: ReferenceLemmaResponse) => void;
  selectLabel?: string;
}) {
  const { query, setQuery, standardOnly, setStandardOnly, state } =
    useReferenceLemmaSearch(code);
  const inputId = useId();
  const standardId = useId();

  return (
    <div className="flex flex-col gap-3">
      <div className="form-field">
        <Label htmlFor={inputId}>Пошук леми або словоформи</Label>
        <Input
          id={inputId}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Почніть вводити слово…"
        />
      </div>

      <label
        className="flex items-center gap-2 text-[0.85rem] text-muted-foreground"
        htmlFor={standardId}
      >
        <Checkbox
          id={standardId}
          checked={standardOnly}
          onCheckedChange={(value) => setStandardOnly(value === true)}
        />
        Лише нормативні леми
      </label>

      {state.status === "searching" && <p role="status">Шукаємо…</p>}
      {state.status === "error" && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === "results" && (
        <ul className="m-0 grid list-none gap-2 p-0">
          {state.results.length === 0 && (
            <li className="lede">Нічого не знайдено.</li>
          )}
          {state.results.map((lemma) => (
            <li key={`${lemma.id}:${lemma.matched_form ?? ""}`}>
              <ReferenceLemmaCard
                lemma={lemma}
                action={
                  onSelect ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      type="button"
                      onClick={() => onSelect(lemma)}
                    >
                      <Plus aria-hidden="true" />
                      {selectLabel}
                    </Button>
                  ) : undefined
                }
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
