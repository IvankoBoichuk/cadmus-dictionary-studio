import { Link, Navigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

import { dictionaryThumbnailUrl, type DictionaryListResponse } from "../api";
import { useAuth } from "../authContext";
import { useDictionaries } from "../hooks/useDictionaries";

type DictionaryEntry = DictionaryListResponse[number];

function Thumbnail({ entry }: { entry: DictionaryEntry }) {
  const pagesStatus = entry.source?.pages_status;
  if (pagesStatus === "completed") {
    return (
      <img
        className="block h-56 w-full bg-secondary object-cover object-top"
        src={dictionaryThumbnailUrl(entry.id)}
        alt=""
        loading="lazy"
        width={256}
        height={224}
      />
    );
  }
  const label =
    pagesStatus === "failed"
      ? "Не вдалося обробити сторінки"
      : "Розбивається на сторінки…";
  return (
    <div className="flex h-56 w-full items-center justify-center bg-secondary p-4 text-center text-[0.88rem] text-muted-foreground">
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
  const handleDelete = () => {
    if (
      window.confirm(
        `Видалити словник «${entry.title ?? "Без назви"}»? Цю дію не можна скасувати.`,
      )
    ) {
      onDelete();
    }
  };

  return (
    <Card asChild className="flex flex-col overflow-hidden">
      <li>
        <Thumbnail entry={entry} />
        <div className="grid gap-2 p-5">
          <p className="status-label">{entry.status === "draft" ? "Чернетка" : "Готовий"}</p>
          <h2 className="mb-0 text-[1.2rem]">{entry.title ?? "Без назви"}</h2>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <Link
              className="inline-block font-[650] text-primary hover:underline"
              to={`/dictionaries/${entry.id}/edit`}
            >
              Редагувати
            </Link>
            <Button
              variant="danger"
              type="button"
              onClick={handleDelete}
              disabled={deletePending}
            >
              {deletePending ? "Видаляємо…" : "Видалити"}
            </Button>
          </div>
          {deleteError && (
            <p className="field-error" role="alert">
              {deleteError}
            </p>
          )}
        </div>
      </li>
    </Card>
  );
}

export function DictionariesList() {
  const { session } = useAuth();
  const { state, deleteState, remove } = useDictionaries();

  if (session.status === "loading") {
    return (
      <main className="page" id="main-content">
        <p role="status">Завантажуємо робочий простір…</p>
      </main>
    );
  }
  if (session.status !== "authenticated") {
    return <Navigate replace to="/login" />;
  }

  return (
    <main className="page" id="main-content">
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
        <ul className="m-0 mt-8 grid list-none grid-cols-[repeat(auto-fill,minmax(16rem,1fr))] gap-5 p-0">
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
    </main>
  );
}
