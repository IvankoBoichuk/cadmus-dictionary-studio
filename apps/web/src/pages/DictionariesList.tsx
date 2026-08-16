import { Link, Navigate } from "react-router-dom";

import { dictionaryThumbnailUrl, type DictionaryListResponse } from "../api";
import { useAuth } from "../authContext";
import { useDictionaries } from "../hooks/useDictionaries";

type DictionaryEntry = DictionaryListResponse[number];

function Thumbnail({ entry }: { entry: DictionaryEntry }) {
  const pagesStatus = entry.source?.pages_status;
  if (pagesStatus === "completed") {
    return (
      <img
        className="dictionary-thumbnail"
        src={dictionaryThumbnailUrl(entry.id)}
        alt=""
        loading="lazy"
      />
    );
  }
  const label =
    pagesStatus === "failed"
      ? "Не вдалося обробити сторінки"
      : "Розбивається на сторінки…";
  return (
    <div className="dictionary-thumbnail dictionary-thumbnail--placeholder">
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
    <li className="dictionary-card">
      <Thumbnail entry={entry} />
      <div className="dictionary-card-body">
        <p className="status-label">{entry.status === "draft" ? "Чернетка" : "Готовий"}</p>
        <h2>{entry.title ?? "Без назви"}</h2>
        <div className="dictionary-card-actions">
          <Link className="secondary-link" to={`/dictionaries/${entry.id}/edit`}>
            Редагувати
          </Link>
          <button
            type="button"
            className="danger-button"
            onClick={handleDelete}
            disabled={deletePending}
          >
            {deletePending ? "Видаляємо…" : "Видалити"}
          </button>
        </div>
        {deleteError && (
          <p className="field-error" role="alert">
            {deleteError}
          </p>
        )}
      </div>
    </li>
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
        <Link className="primary-link" to="/dictionaries/new">
          Додати словник
        </Link>
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
        <ul className="dictionary-grid">
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
