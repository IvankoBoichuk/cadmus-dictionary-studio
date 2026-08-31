import { ArrowRight, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

import { dictionaryThumbnailUrl, type DictionaryListResponse } from "../api";
import {
  DICTIONARY_STATUS_BADGE_VARIANT,
  DICTIONARY_STATUS_LABELS,
} from "../dictionaryStatusLabels";
import { useDictionaries } from "../hooks/useDictionaries";

type DictionaryEntry = DictionaryListResponse[number];

/** Cover art box — the whole cover is shown (`object-contain`), never cropped.
 * The card has no text title, so the cover image carries its name via `alt`. */
function Cover({ entry, title }: { entry: DictionaryEntry; title: string }) {
  const pagesStatus = entry.source?.pages_status;
  if (pagesStatus === "completed") {
    return (
      <img
        className="h-full w-full object-contain"
        src={dictionaryThumbnailUrl(entry.id)}
        alt={title}
        loading="lazy"
        width={264}
        height={352}
      />
    );
  }
  const label =
    pagesStatus === "failed"
      ? "Не вдалося обробити сторінки"
      : "Розбивається на сторінки…";
  return (
    <div className="flex h-full w-full items-center justify-center p-4 text-center text-[0.88rem] text-muted-foreground">
      <span>{label}</span>
    </div>
  );
}

function DictionaryCard({
  entry,
  onDelete,
  deletePending,
  deleteError,
}: {
  entry: DictionaryEntry;
  onDelete: () => void;
  deletePending: boolean;
  deleteError: string | undefined;
}) {
  const title = entry.title ?? "Без назви";

  const handleDelete = () => {
    if (
      window.confirm(
        `Видалити словник «${title}»? Цю дію не можна скасувати.`,
      )
    ) {
      onDelete();
    }
  };

  return (
    <Card asChild className="group relative flex flex-col overflow-hidden">
      <li>
        <div className="relative aspect-3/4 w-full bg-secondary">
          <Cover entry={entry} title={title} />
          <Badge
            className="absolute top-2 left-2 shadow-sm"
            variant={DICTIONARY_STATUS_BADGE_VARIANT[entry.status]}
          >
            {DICTIONARY_STATUS_LABELS[entry.status]}
          </Badge>
          <div className="absolute top-2 right-2 flex gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100">
            <Button
              asChild
              size="icon"
              variant="secondary"
              className="size-9 shadow-sm"
            >
              <Link to={`/dictionaries/${entry.id}`} aria-label="Відкрити">
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
            <Button
              type="button"
              size="icon"
              variant="danger"
              className="size-9 shadow-sm"
              aria-label="Видалити"
              onClick={handleDelete}
              disabled={deletePending}
            >
              <Trash2 aria-hidden="true" />
            </Button>
          </div>
        </div>
        {deleteError && (<div className="p-4">
          <p className="field-error" role="alert">
            {deleteError}
          </p>
        </div>)}
      </li>
    </Card>
  );
}

export function DictionariesList() {
  const { state, deleteState, remove } = useDictionaries();

  return (
    <>
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Словники</p>
        <h1 id="page-title">Мої словники</h1>
        <p className="lede">
          Тут відображаються всі словники, які ви завантажили або створили.
        </p>
        <Button asChild className="mt-4 px-[1.1rem] py-3">
          <Link to="/dictionaries/new">Додати словник</Link>
        </Button>
      </section>

      {state.status === "loading" && <p role="status">Завантажуємо словники…</p>}
      {state.status === "error" && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === "loaded" && state.dictionaries.length === 0 && (
        <p className="lede">Ви ще не завантажили жодного словника.</p>
      )}
      {state.status === "loaded" && state.dictionaries.length > 0 && (
        <ul className="m-0 mt-8 grid list-none grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-5 p-0">
          {state.dictionaries.map((entry) => (
            <DictionaryCard
              key={entry.id}
              entry={entry}
              onDelete={() => void remove(entry.id)}
              deletePending={deleteState[entry.id]?.pending ?? false}
              deleteError={deleteState[entry.id]?.error}
            />
          ))}
        </ul>
      )}
    </>
  );
}
