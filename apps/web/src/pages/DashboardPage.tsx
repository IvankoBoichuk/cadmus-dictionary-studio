import { CircleCheck, FilePen, Library, ScanLine } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

import type { DictionaryResponse } from "../api";
import { useAuth } from "../authContext";
import {
  DICTIONARY_STATUS_BADGE_VARIANT,
  DICTIONARY_STATUS_LABELS,
} from "../dictionaryStatusLabels";
import { formatDate, formatNumber } from "../format";
import { useDictionaries } from "../hooks/useDictionaries";

const RECENT_LIMIT = 5;

export function DashboardPage() {
  const { session } = useAuth();
  const { state } = useDictionaries();

  const email = session.status === "authenticated" ? session.user.email : "";
  const dictionaries = state.status === "loaded" ? state.dictionaries : [];
  const loading = state.status === "loading";

  const countByStatus = (status: DictionaryResponse["status"]) =>
    dictionaries.filter((entry) => entry.status === status).length;

  const recent = [...dictionaries]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, RECENT_LIMIT);

  return (
    <>
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Панель</p>
        <h1 id="page-title">Робочий простір</h1>
        <p className="lede">
          Ви увійшли як {email}. Огляд ваших словників і швидкі дії.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button asChild className="px-[1.1rem] py-3">
            <Link to="/dictionaries/new">Додати словник</Link>
          </Button>
          <Button asChild variant="secondary" className="px-[1.1rem] py-3">
            <Link to="/dictionaries">Усі словники</Link>
          </Button>
        </div>
      </section>

      {state.status === "error" ? (
        <p className="form-error mt-8" role="alert">
          {state.message}
        </p>
      ) : state.status === "loaded" && dictionaries.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <section
            aria-labelledby="metrics-title"
            className="mt-[clamp(2rem,6vw,3.5rem)]"
          >
            <h2 id="metrics-title" className="sr-only">
              Показники
            </h2>
            {loading && (
              <p role="status" className="sr-only">
                Завантажуємо словники…
              </p>
            )}
            <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(11rem,1fr))]">
              <MetricCard
                label="Усього словників"
                value={dictionaries.length}
                icon={Library}
                loading={loading}
              />
              <MetricCard
                label="Чернетки"
                value={countByStatus("draft")}
                icon={FilePen}
                loading={loading}
              />
              <MetricCard
                label="Готові до обробки"
                value={countByStatus("configured")}
                icon={CircleCheck}
                loading={loading}
              />
              <MetricCard
                label="Скановані"
                value={countByStatus("scanned")}
                icon={ScanLine}
                loading={loading}
              />
            </div>
          </section>

          <section
            aria-labelledby="recent-title"
            className="mt-[clamp(2rem,6vw,3.5rem)]"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h2 id="recent-title" className="mb-0 text-[1.3rem]">
                Останні словники
              </h2>
              <Link
                className="font-[650] text-primary hover:underline"
                to="/dictionaries"
              >
                Переглянути всі
              </Link>
            </div>
            {loading ? (
              <p className="mt-4 text-muted-foreground">Завантажуємо словники…</p>
            ) : (
              <Card className="mt-4 overflow-hidden">
                <ul className="m-0 list-none divide-y p-0">
                  {recent.map((entry) => (
                    <RecentRow key={entry.id} entry={entry} />
                  ))}
                </ul>
              </Card>
            )}
          </section>
        </>
      )}
    </>
  );
}

function MetricCard({
  label,
  value,
  icon: Icon,
  loading,
}: {
  label: string;
  value: number;
  icon: typeof Library;
  loading: boolean;
}) {
  return (
    <Card className="flex items-start justify-between gap-3 p-5">
      <div>
        <p className="eyebrow">{label}</p>
        {loading ? (
          <span
            aria-hidden="true"
            className="mt-2 block h-7 w-14 animate-pulse rounded bg-secondary"
          />
        ) : (
          <p className="mt-1 mb-0 font-serif text-[2rem] leading-none">
            {formatNumber(value)}
          </p>
        )}
      </div>
      <span
        aria-hidden="true"
        className="flex size-9 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground"
      >
        <Icon className="size-[1.15rem]" />
      </span>
    </Card>
  );
}

function RecentRow({ entry }: { entry: DictionaryResponse }) {
  const blockers = entry.readiness_blockers.length;
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 p-4 sm:p-5">
      <Link
        className="font-[650] text-primary hover:underline"
        to={`/dictionaries/${entry.id}/edit`}
      >
        {entry.title ?? "Без назви"}
      </Link>
      <Badge variant={DICTIONARY_STATUS_BADGE_VARIANT[entry.status]}>
        {DICTIONARY_STATUS_LABELS[entry.status]}
      </Badge>
      {blockers > 0 && (
        <Badge variant="warning">
          Потребує уваги: {formatNumber(blockers)}
        </Badge>
      )}
      <span className="ml-auto text-[0.85rem] text-muted-foreground">
        Оновлено {formatDate(entry.updated_at)}
      </span>
    </li>
  );
}

function EmptyState() {
  return (
    <Card className="mt-[clamp(2rem,6vw,3.5rem)] grid justify-items-center gap-3 p-[clamp(1.5rem,5vw,2.5rem)] text-center">
      <span
        aria-hidden="true"
        className="flex size-12 items-center justify-center rounded-full bg-secondary text-secondary-foreground"
      >
        <Library className="size-6" />
      </span>
      <h2 className="mb-0 text-[1.3rem]">Ще немає словників</h2>
      <p className="mb-2 max-w-[34rem] text-muted-foreground [text-wrap:pretty]">
        Завантажте скан або PDF друкованого словника — Cadmus розіб’є його на
        сторінки й допоможе виділити статті.
      </p>
      <Button asChild className="px-[1.1rem] py-3">
        <Link to="/dictionaries/new">Додати словник</Link>
      </Button>
    </Card>
  );
}
