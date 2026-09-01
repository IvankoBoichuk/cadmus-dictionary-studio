import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";

import {
  API,
  ApiError,
  apiMessageFrom,
  isAbortError,
  type ReferenceLexiconResponse,
} from "../api";
import { ReferenceLemmaSearchCombobox } from "../components/ReferenceLemmaSearchCombobox";
import { formatDate } from "../format";

type LoadState =
  | { status: "loading" }
  | { status: "loaded"; lexicon: ReferenceLexiconResponse }
  | { status: "missing" }
  | { status: "error"; message: string };

function MetaRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-0.5">
      <dt className="text-[0.68rem] font-[700] tracking-[0.08em] text-muted-foreground uppercase">
        {label}
      </dt>
      <dd className="m-0 text-[0.9rem] [overflow-wrap:anywhere]">{children}</dd>
    </div>
  );
}

function ReferenceLexiconWorkspace({ code }: { code: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    API.referenceLexicons.get(code, { signal: controller.signal }).then(
      (lexicon) => setState({ status: "loaded", lexicon }),
      (error: unknown) => {
        if (isAbortError(error)) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: "missing" });
          return;
        }
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ??
            "Не вдалося завантажити довідковий словник. Спробуйте пізніше.",
        });
      },
    );
    return () => controller.abort();
  }, [code]);

  if (state.status === "loading") {
    return <p role="status">Завантажуємо довідковий словник…</p>;
  }
  if (state.status === "missing") {
    return (
      <div className="form-section">
        <h1 className="!mb-2 text-[1.4rem]">Довідковий словник «{code}»</h1>
        <p className="lede">
          Цей довідковий словник ще не імпортовано. Зверніться до адміністратора,
          щоб виконати імпорт вибраної версії VESUM.
        </p>
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <p className="form-error" role="alert">
        {state.message}
      </p>
    );
  }

  const { lexicon } = state;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:items-start">
      <aside className="min-w-0">
        <div className="form-section">
          <p className="text-[0.7rem] font-[750] tracking-[0.12em] text-muted-foreground uppercase">
            Довідковий лексикон
          </p>
          <h1 className="mt-0.5 mb-1 font-serif text-[1.4rem] leading-tight font-medium">
            {lexicon.name}
          </h1>
          <div className="mb-3 flex flex-wrap gap-1.5">
            <Badge variant="info" className="font-mono">
              {lexicon.code}
            </Badge>
            <Badge variant="secondary">{lexicon.language_code}</Badge>
          </div>
          <dl className="grid gap-2.5">
            <MetaRow label="Версія">{lexicon.version}</MetaRow>
            <MetaRow label="Ліцензія">{lexicon.license_id}</MetaRow>
            <MetaRow label="Імпортовано">
              {formatDate(lexicon.imported_at)}
            </MetaRow>
            {lexicon.source_commit && (
              <MetaRow label="Коміт джерела">
                <span className="font-mono text-[0.8rem]">
                  {lexicon.source_commit}
                </span>
              </MetaRow>
            )}
            <MetaRow label="Джерело">
              <a
                href={lexicon.source_url}
                target="_blank"
                rel="noreferrer"
                className="text-primary"
              >
                {lexicon.source_url}
              </a>
            </MetaRow>
            <MetaRow label="Контрольна сума">
              <span className="font-mono text-[0.78rem]">{lexicon.checksum}</span>
            </MetaRow>
          </dl>
        </div>
      </aside>

      <div className="form-section">
        <h2>Пошук лем і словоформ</h2>
        <p className="section-hint">
          Знайдіть нормативну лему або її словоформу. Прив'язати лему до статті
          можна на сторінці самої статті.
        </p>
        <ReferenceLemmaSearchCombobox code={lexicon.code} />
      </div>
    </div>
  );
}

export function ReferenceLexiconPage() {
  const { code } = useParams<{ code: string }>();

  if (!code) {
    return <Navigate replace to="/dictionaries" />;
  }

  return <ReferenceLexiconWorkspace code={code} />;
}
