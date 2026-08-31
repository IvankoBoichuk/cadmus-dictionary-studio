import { useOutletContext } from "react-router-dom";

import type { DictionaryResponse } from "../api";

export type DictionaryContext = {
  dictionary: DictionaryResponse;
  onUpdated: (dictionary: DictionaryResponse) => void;
};

/** Dictionary loaded by `DictionaryLayout`, shared with its nested routes. */
export function useDictionaryContext(): DictionaryContext {
  return useOutletContext<DictionaryContext>();
}
