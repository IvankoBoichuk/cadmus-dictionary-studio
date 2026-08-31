import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { DictionaryMetadataForm } from "../components/DictionaryMetadataForm";
import { DictionaryReadiness } from "../components/DictionaryReadiness";
import { DictionarySourceUpload } from "../components/DictionarySourceUpload";
import type { DictionaryResponse } from "../api";
import { useDictionary } from "../hooks/useDictionary";

const METADATA_DESCRIPTION =
  "Бібліографічні, мовні та правові дані. Чернетку можна зберігати неповною й повертатися до неї пізніше.";

function NewDictionaryFlow() {
  const [uploaded, setUploaded] = useState<DictionaryResponse | null>(null);
  const handleUploaded = useCallback((dictionary: DictionaryResponse) => {
    setUploaded(dictionary);
  }, []);

  if (!uploaded) {
    return (
      <>
        <header className="mb-6">
          <p className="text-[0.7rem] font-[750] tracking-[0.12em] text-muted-foreground uppercase">
            Словник
          </p>
          <h1 className="mt-0.5 mb-0 max-w-none font-serif text-[1.6rem] leading-tight font-medium">
            Додати словник
          </h1>
        </header>
        <DictionarySourceUpload onUploaded={handleUploaded} />
      </>
    );
  }
  return (
    <DictionaryMetadataForm
      initialDictionary={uploaded}
      source={uploaded.source}
      title="Додати словник"
      description={METADATA_DESCRIPTION}
    />
  );
}

function DictionarySectionNav({ dictionaryId }: { dictionaryId: string }) {
  const links = [
    { to: `/dictionaries/${dictionaryId}/page-ranges`, label: "Діапазони сторінок" },
    {
      to: `/dictionaries/${dictionaryId}/abbreviations`,
      label: "Скорочення словника",
    },
    {
      to: `/dictionaries/${dictionaryId}/settlements`,
      label: "Географічні мітки",
    },
    {
      to: `/dictionaries/${dictionaryId}/article-schema`,
      label: "Схема словникової статті",
    },
    { to: `/dictionaries/${dictionaryId}/view`, label: "Переглянути сторінки" },
    { to: `/dictionaries/${dictionaryId}/members`, label: "Учасники проєкту" },
  ];
  return (
    <nav
      className="mb-6 flex flex-wrap gap-x-4 gap-y-2 text-[0.9rem]"
      aria-label="Розділи словника"
    >
      {links.map((link) => (
        <Link
          key={link.to}
          className="font-[650] text-primary hover:underline"
          to={link.to}
        >
          {link.label}
        </Link>
      ))}
    </nav>
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
    <DictionaryMetadataForm
      initialDictionary={dictionary}
      source={dictionary.source}
      onSaved={setOverride}
      title="Редагувати метадані словника"
      description={METADATA_DESCRIPTION}
      statusSlot={
        <DictionaryReadiness
          dictionary={dictionary}
          onConfigured={setOverride}
          onScanned={setOverride}
        />
      }
      navSlot={<DictionarySectionNav dictionaryId={dictionaryId} />}
    />
  );
}

export function DictionaryFormPage() {
  const { dictionaryId } = useParams<{ dictionaryId?: string }>();

  return dictionaryId ? (
    <ExistingDictionaryFlow dictionaryId={dictionaryId} />
  ) : (
    <NewDictionaryFlow />
  );
}
