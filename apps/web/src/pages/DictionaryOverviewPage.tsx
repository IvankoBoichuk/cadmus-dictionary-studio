import { useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

import type { DictionaryResponse } from "../api";
import { useDictionaryContext } from "../components/dictionaryContext";
import { DictionaryReadiness } from "../components/DictionaryReadiness";
import {
  CONTRIBUTOR_ROLE_LABELS,
  LEGAL_STATUS_LABELS,
} from "../dictionaryLabels";
import { formatNumber, formatPercent } from "../format";
import { useDictionaryPagesSummary } from "../hooks/useDictionaryPagesSummary";
import { useScanProgress } from "../hooks/useScanProgress";
import { formatLanguages } from "../languageOptions";

function MetricCard({ label, value }: { label: string; value: number | null }) {
  return (
    <Card className="grid gap-1 p-5">
      <p className="text-[0.7rem] font-[750] tracking-[0.12em] text-muted-foreground uppercase">
        {label}
      </p>
      <p className="mb-0 font-serif text-[2rem] leading-none">
        {value === null ? "—" : formatNumber(value)}
      </p>
    </Card>
  );
}

/** North-star bar: how much of the dictionary is finished ("complete"). */
function CompletionBar({
  label,
  completed,
  total,
  to,
}: {
  label: string;
  completed: number | null;
  total: number | null;
  to?: string;
}) {
  const known = completed !== null && total !== null;
  const ratio = known && total > 0 ? completed / total : 0;
  return (
    <div className="grid gap-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        {to ? (
          <Link to={to} className="font-[650] text-primary">
            {label}
          </Link>
        ) : (
          <span className="font-[650]">{label}</span>
        )}
        <span className="text-[0.9rem] text-muted-foreground tabular-nums">
          {!known
            ? "—"
            : total === 0
              ? "ще немає"
              : `${formatNumber(completed)} / ${formatNumber(total)} · ${formatPercent(ratio)}`}
        </span>
      </div>
      <Progress
        value={Math.round(ratio * 100)}
        aria-label={`${label}: опрацьовано`}
      />
    </div>
  );
}

function MetaRow({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="grid gap-0.5 border-t border-border py-2 first:border-t-0 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-4">
      <dt className="font-[650] text-muted-foreground">{term}</dt>
      <dd className="m-0 [overflow-wrap:anywhere] whitespace-pre-line">
        {children}
      </dd>
    </div>
  );
}

/** Every field from the metadata form, in the same order, "—" when unset. */
function DictionaryMetadata({ dictionary }: { dictionary: DictionaryResponse }) {
  const dash = (value: string | null) => (value?.trim() ? value : "—");
  const legal = dictionary.legal_status;

  return (
    <dl className="m-0 text-[0.95rem]">
      <MetaRow term="Назва">{dash(dictionary.title)}</MetaRow>
      <MetaRow term="Опис">{dash(dictionary.description)}</MetaRow>
      <MetaRow term="Структура статті">
        {dash(dictionary.article_description)}
      </MetaRow>
      <MetaRow term="Тип словника">{dash(dictionary.dictionary_type)}</MetaRow>
      <MetaRow term="Видавництво">{dash(dictionary.publisher)}</MetaRow>
      <MetaRow term="Рік видання">
        {dictionary.publication_year?.toString() ?? "—"}
      </MetaRow>
      <MetaRow term="Видання">{dash(dictionary.edition)}</MetaRow>
      <MetaRow term="ISBN">{dash(dictionary.isbn)}</MetaRow>
      <MetaRow term="Джерело цифрової копії">
        {dash(dictionary.digital_source)}
      </MetaRow>
      <MetaRow term="Автори та укладачі">
        {dictionary.contributors.length === 0
          ? "—"
          : dictionary.contributors
              .map(
                (contributor) =>
                  `${contributor.name} (${CONTRIBUTOR_ROLE_LABELS[contributor.role] ?? contributor.role})`,
              )
              .join(", ")}
      </MetaRow>
      <MetaRow term="Мови">
        {dictionary.language_codes.length === 0
          ? "—"
          : formatLanguages(dictionary.language_codes)}
      </MetaRow>
      <MetaRow term="Правовий статус">
        {legal ? (LEGAL_STATUS_LABELS[legal] ?? legal) : "—"}
      </MetaRow>
      {legal === "licensed" && (
        <MetaRow term="Тип ліцензії">{dash(dictionary.license_type)}</MetaRow>
      )}
      {legal === "permission_granted" && (
        <MetaRow term="Опис дозволу">
          {dash(dictionary.permission_reference)}
        </MetaRow>
      )}
      <MetaRow term="Примітка щодо прав">{dash(dictionary.rights_note)}</MetaRow>
    </dl>
  );
}

export function DictionaryOverviewPage() {
  const { dictionary, onUpdated } = useDictionaryContext();
  const summary = useDictionaryPagesSummary(dictionary.id);
  const progress = useScanProgress(dictionary.id, 0);

  const scan = progress.status === "loaded" ? progress.progress : null;

  // Reading progress auto-advances the dictionary status server-side
  // (scanned -> in_progress -> processed); reflect that in the shared header.
  const syncedStatus = scan?.status;
  useEffect(() => {
    if (syncedStatus && syncedStatus !== dictionary.status) {
      onUpdated({ ...dictionary, status: syncedStatus });
    }
  }, [syncedStatus, dictionary, onUpdated]);

  const totalPages = summary.status === "loaded" ? summary.totalPages : null;
  const processedPages = scan?.processed_pages ?? null;
  const pagesWithWords =
    scan?.pages.filter((page) => page.has_lexemes).length ?? null;

  return (
    <div className="grid gap-6">
      <section aria-labelledby="overview-status-heading" className="grid gap-3">
        <h2 id="overview-status-heading" className="sr-only">
          Стан словника
        </h2>
        <DictionaryReadiness
          dictionary={dictionary}
          onConfigured={onUpdated}
          onScanned={onUpdated}
          onPublished={onUpdated}
        />
      </section>

      <section aria-labelledby="overview-progress-heading" className="grid gap-4">
        <h2 id="overview-progress-heading" className="mb-0 text-[1.15rem]">
          Прогрес опрацювання
        </h2>
        <Card className="grid gap-4 p-[clamp(1.25rem,4vw,2rem)]">
          <CompletionBar
            label="Лексеми"
            completed={scan?.completed_lexemes ?? null}
            total={scan?.total_lexemes ?? null}
          />
          <CompletionBar
            label="Статті"
            completed={scan?.completed_entries ?? null}
            total={scan?.total_entries ?? null}
            to="entries"
          />
        </Card>
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(12rem,1fr))]">
          <MetricCard label="Сторінок у діапазонах" value={totalPages} />
          <MetricCard label="Опрацьовано сторінок" value={processedPages} />
          <MetricCard label="Сторінок зі словами" value={pagesWithWords} />
        </div>
        {(summary.status === "error" || progress.status === "error") && (
          <p className="form-error" role="alert">
            {summary.status === "error"
              ? summary.message
              : progress.status === "error"
                ? progress.message
                : null}
          </p>
        )}
      </section>

      <Card
        className="grid gap-3 p-[clamp(1.25rem,4vw,2rem)]"
        aria-labelledby="overview-metadata-heading"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 id="overview-metadata-heading" className="mb-0 text-[1.15rem]">
            Про словник
          </h2>
          <Link
            className="text-[0.9rem] font-[650] text-primary hover:underline"
            to="settings/metadata"
          >
            Редагувати
          </Link>
        </div>
        <DictionaryMetadata dictionary={dictionary} />
        <div className="mt-2">
          <Button asChild>
            <Link to="pages">Перейти до опрацювання</Link>
          </Button>
        </div>
      </Card>
    </div>
  );
}
