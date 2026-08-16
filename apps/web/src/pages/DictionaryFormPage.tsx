import { useCallback, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";

import { useAuth } from "../authContext";
import { DictionaryMetadataForm } from "../components/DictionaryMetadataForm";
import { DictionarySourceUpload } from "../components/DictionarySourceUpload";
import type { DictionaryResponse } from "../api";
import { useDictionary } from "../hooks/useDictionary";

function NewDictionaryFlow() {
  const [uploaded, setUploaded] = useState<DictionaryResponse | null>(null);
  const handleUploaded = useCallback((dictionary: DictionaryResponse) => {
    setUploaded(dictionary);
  }, []);

  if (!uploaded) {
    return <DictionarySourceUpload onUploaded={handleUploaded} />;
  }
  return (
    <DictionaryMetadataForm initialDictionary={uploaded} source={uploaded.source} />
  );
}

function ExistingDictionaryFlow({ dictionaryId }: { dictionaryId: string }) {
  const state = useDictionary(dictionaryId);

  if (state.status === "loading") {
    return <p role="status">Завантажуємо словник…</p>;
  }
  if (state.status === "error") {
    return (
      <p className="form-error" role="alert">
        {state.message}
      </p>
    );
  }
  return (
    <>
      <div className="form-actions">
        <Link className="secondary-link" to={`/dictionaries/${dictionaryId}/abbreviations`}>
          Налаштувати скорочення словника
        </Link>
      </div>
      <DictionaryMetadataForm
        initialDictionary={state.dictionary}
        source={state.dictionary.source}
      />
    </>
  );
}

export function DictionaryFormPage() {
  const { session } = useAuth();
  const { dictionaryId } = useParams<{ dictionaryId?: string }>();

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
        <p className="eyebrow">Словник</p>
        <h1 id="page-title">
          {dictionaryId ? "Редагувати метадані словника" : "Додати словник"}
        </h1>
        <p className="lede">
          Завантажте PDF і заповніть бібліографічні, мовні та правові дані.
          Чернетку можна зберігати неповною й повертатися до неї пізніше.
        </p>
      </section>
      <div className="dictionary-form">
        {dictionaryId ? (
          <ExistingDictionaryFlow dictionaryId={dictionaryId} />
        ) : (
          <NewDictionaryFlow />
        )}
      </div>
    </main>
  );
}
