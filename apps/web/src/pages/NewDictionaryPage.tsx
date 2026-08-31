import { useCallback, useState } from "react";

import { DictionaryMetadataForm } from "../components/DictionaryMetadataForm";
import { DictionarySourceUpload } from "../components/DictionarySourceUpload";
import type { DictionaryResponse } from "../api";

/** `/dictionaries/new` — upload a source PDF, then fill in the draft metadata.
 * Editing an existing dictionary lives under `DictionaryLayout` instead. */
export function NewDictionaryPage() {
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
    />
  );
}
