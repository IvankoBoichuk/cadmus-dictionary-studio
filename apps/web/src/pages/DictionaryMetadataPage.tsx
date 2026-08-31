import { DictionaryMetadataForm } from "../components/DictionaryMetadataForm";
import { useDictionaryContext } from "../components/dictionaryContext";

/** `/dictionaries/:id/settings/metadata` — the bibliographic form, with its
 * Save action portalled into the shared `DictionaryLayout` header. */
export function DictionaryMetadataPage() {
  const { dictionary, onUpdated } = useDictionaryContext();

  return (
    <DictionaryMetadataForm
      key={dictionary.id}
      initialDictionary={dictionary}
      source={dictionary.source}
      onSaved={onUpdated}
      portalActionsInto="dictionary-header-actions"
    />
  );
}
