import { useCallback, useEffect, useState } from "react";

import { API, apiMessageFrom, isAbortError, type ArticleSchemaResponse } from "../api";

export type ArticleSchemasLoadState =
  | { status: "loading" }
  | { status: "loaded"; schemas: ArticleSchemaResponse[] }
  | { status: "error"; message: string };

/** Loads a dictionary's article-schema version history (BH-148). */
export function useArticleSchemas(dictionaryId: string) {
  const [state, setState] = useState<ArticleSchemasLoadState>({ status: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    API.articleSchemas.list(dictionaryId, { signal: controller.signal }).then(
      (schemas) => setState({ status: "loaded", schemas }),
      (error: unknown) => {
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ??
            "Не вдалося завантажити версії схеми статті. Спробуйте пізніше.",
        });
      },
    );
    return () => controller.abort();
  }, [dictionaryId, reloadToken]);

  const upsert = useCallback((item: ArticleSchemaResponse) => {
    setState((current) =>
      current.status === "loaded"
        ? {
            status: "loaded",
            schemas: current.schemas.some((schema) => schema.id === item.id)
              ? current.schemas.map((schema) => (schema.id === item.id ? item : schema))
              : [...current.schemas, item],
          }
        : current,
    );
  }, []);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  return { state, upsert, reload } as const;
}
