import { ExternalLink, Plus, Trash2 } from "lucide-react";
import { useId, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import { apiMessageFrom, type ReferenceRelationType } from "../api";
import { useEntryReferenceLinks } from "../hooks/useEntryReferenceLinks";
import { RELATION_TYPE_LABELS, RELATION_TYPE_ORDER } from "../referenceLabels";
import { ReferenceLemmaCard } from "./ReferenceLemmaCard";
import { ReferenceLemmaSearchCombobox } from "./ReferenceLemmaSearchCombobox";

/** Reference lexicon Cadmus ships support for (ADR-0009). */
export const VESUM_CODE = "vesum";

export function EntryReferenceLinksSection({ entryId }: { entryId: string }) {
  const { state, add, remove, removingId } = useEntryReferenceLinks(entryId);
  const [addOpen, setAddOpen] = useState(false);
  const [relationType, setRelationType] =
    useState<ReferenceRelationType>("standard_equivalent");
  const [addError, setAddError] = useState<string | null>(null);
  const relationSelectId = useId();

  const handleSelect = async (referenceLemmaId: string) => {
    setAddError(null);
    try {
      await add(referenceLemmaId, relationType);
      setAddOpen(false);
    } catch (error) {
      setAddError(
        apiMessageFrom(error) ??
          "Не вдалося прив'язати лему. Спробуйте пізніше.",
      );
    }
  };

  const handleRemove = async (linkId: string) => {
    if (!window.confirm("Вилучити цю прив'язку до довідкового словника?")) return;
    try {
      await remove(linkId);
    } catch {
      // The row stays; a transient failure is recoverable on retry.
    }
  };

  return (
    <div className="form-section">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="!mb-0">Довідковий лексикон (VESUM)</h2>
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link to={`/reference-lexicons/${VESUM_CODE}`}>
              <ExternalLink aria-hidden="true" />
              Переглянути довідник
            </Link>
          </Button>
          <Popover
            open={addOpen}
            onOpenChange={(open) => {
              setAddOpen(open);
              if (!open) setAddError(null);
            }}
          >
            <PopoverTrigger asChild>
              <Button variant="secondary" size="sm" type="button">
                <Plus aria-hidden="true" />
                Додати відповідник
              </Button>
            </PopoverTrigger>
            <PopoverContent className="max-h-[70vh] w-[min(92vw,30rem)] overflow-y-auto">
              <div className="form-field mb-3">
                <label htmlFor={relationSelectId}>Тип зв'язку</label>
                <select
                  id={relationSelectId}
                  value={relationType}
                  onChange={(event) =>
                    setRelationType(
                      event.target.value as ReferenceRelationType,
                    )
                  }
                >
                  {RELATION_TYPE_ORDER.map((value) => (
                    <option key={value} value={value}>
                      {RELATION_TYPE_LABELS[value]}
                    </option>
                  ))}
                </select>
                {relationType === "standard_equivalent" && (
                  <p className="section-hint m-0 mt-1">
                    Для літературного відповідника потрібна нормативна лема.
                  </p>
                )}
              </div>
              <ReferenceLemmaSearchCombobox
                code={VESUM_CODE}
                onSelect={(lemma) => void handleSelect(lemma.id)}
              />
              {addError && (
                <p className="form-error mt-2" role="alert">
                  {addError}
                </p>
              )}
            </PopoverContent>
          </Popover>
        </div>
      </div>

      <p className="section-hint">
        Підтверджені зв'язки статті з нормативними лемами сучасної української
        мови. Не змінюють транскрипцію джерела.
      </p>

      {state.status === "loading" && (
        <p role="status">Завантажуємо прив'язки…</p>
      )}
      {state.status === "error" && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === "loaded" &&
        (state.links.length === 0 ? (
          <p className="lede">
            Прив'язок ще немає. Знайдіть лему у VESUM і підтвердьте відповідність.
          </p>
        ) : (
          <ul className="m-0 grid list-none gap-2 p-0">
            {state.links.map((link) => (
              <li key={link.id} className="grid gap-1">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">
                    {RELATION_TYPE_LABELS[link.relation_type]}
                  </Badge>
                </div>
                <ReferenceLemmaCard
                  lemma={link.lemma}
                  action={
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon-sm"
                          variant="danger"
                          type="button"
                          disabled={removingId === link.id}
                          onClick={() => void handleRemove(link.id)}
                          aria-label="Вилучити прив'язку"
                        >
                          <Trash2 aria-hidden="true" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Вилучити прив'язку</TooltipContent>
                    </Tooltip>
                  }
                />
              </li>
            ))}
          </ul>
        ))}
    </div>
  );
}
