import { useCallback, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";

import { useAuth } from "../authContext";
import { DictionaryMetadataForm } from "../components/DictionaryMetadataForm";
import { DictionaryReadiness } from "../components/DictionaryReadiness";
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
  const [override, setOverride] = useState<DictionaryResponse | null>(null);
  const dictionary = override ?? (state.status === "loaded" ? state.dictionary : null);

  if (state.status === "error") {
    return (
      <p className="form-error" role="alert">
        {state.message}
      </p>
    );
  }
  if (state.status === "loading" || !dictionary) {
    return <p role="status">Завантажуємо словник…</p>;
  }
  return (
    <>
      <div className="form-actions">
        <Link
          className="ml-4 inline-block font-[650] text-primary hover:underline"
          to={`/dictionaries/${dictionaryId}/page-ranges`}
        >
          Налаштувати діапазони сторінок
        </Link>
        <Link
          className="ml-4 inline-block font-[650] text-primary hover:underline"
          to={`/dictionaries/${dictionaryId}/abbreviations`}
        >
          Налаштувати скорочення словника
        </Link>
        <Link
          className="ml-4 inline-block font-[650] text-primary hover:underline"
          to={`/dictionaries/${dictionaryId}/settlements`}
        >
          Зіставити географічні мітки словника
        </Link>
        <Link
          className="ml-4 inline-block font-[650] text-primary hover:underline"
          to={`/dictionaries/${dictionaryId}/article-schema`}
        >
          Схема словникової статті
        </Link>
        <Link
          className="ml-4 inline-block font-[650] text-primary hover:underline"
          to={`/dictionaries/${dictionaryId}/view`}
        >
          Переглянути сторінки
        </Link>
        <Link
          className="ml-4 inline-block font-[650] text-primary hover:underline"
          to={`/dictionaries/${dictionaryId}/members`}
        >
          Учасники проєкту
        </Link>
      </div>
      <DictionaryReadiness
        dictionary={dictionary}
        onConfigured={setOverride}
        onScanned={setOverride}
      />
      <DictionaryMetadataForm
        initialDictionary={dictionary}
        source={dictionary.source}
        onSaved={setOverride}
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
