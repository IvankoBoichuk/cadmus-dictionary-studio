import { useMemo, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

import type { EntryStatus, EntrySummaryResponse } from "../api";
import {
  ENTRY_STATUS_LABELS,
  ENTRY_STATUS_ORDER,
  ENTRY_STATUS_VARIANT,
} from "../entryStatusLabels";
import { formatDate } from "../format";
import { useDictionaryEntries } from "../hooks/useDictionaryEntries";

const COMPACT =
  "text-[0.85rem] [&_th]:px-2 [&_th]:py-1 [&_td]:px-2 [&_td]:py-1 [&_td]:align-middle";

type Filter = EntryStatus | "all";

function EntriesWorkspace({ dictionaryId }: { dictionaryId: string }) {
  const { state } = useDictionaryEntries(dictionaryId);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const allEntries = useMemo(
    () => (state.status === "loaded" ? state.entries : []),
    [state],
  );

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return allEntries.filter((entry) => {
      if (filter !== "all" && entry.status !== filter) return false;
      if (needle && !entry.headword.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [allEntries, filter, query]);

  return (
    <>
      <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="mb-2 text-[1.15rem]">Статті словника</h2>
          <p className="max-w-[60ch] text-[0.9rem] text-muted-foreground">
            Усі структуровані статті цього словника. Натисніть заголовне слово,
            щоб відкрити й відредагувати поля статті.
          </p>
        </div>
        <label className="w-full max-w-xs">
          <span className="sr-only">Пошук за заголовним словом</span>
          <Input
            type="search"
            placeholder="Пошук за заголовним словом…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      </div>

      <div className="dictionary-form">
        <div
          className="flex flex-wrap gap-1"
          role="group"
          aria-label="Фільтр за статусом"
        >
          {(["all", ...ENTRY_STATUS_ORDER] as Filter[]).map((value) => {
            const active = filter === value;
            const count =
              value === "all"
                ? allEntries.length
                : allEntries.filter((entry) => entry.status === value).length;
            return (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={active ? "default" : "secondary"}
                aria-pressed={active}
                onClick={() => setFilter(value)}
              >
                {value === "all" ? "Усі" : ENTRY_STATUS_LABELS[value]}
                <span className="ml-1.5 tabular-nums opacity-70">{count}</span>
              </Button>
            );
          })}
        </div>

        {state.status === "loading" && (
          <p role="status">Завантажуємо статті…</p>
        )}
        {state.status === "error" && (
          <p className="form-error" role="alert">
            {state.message}
          </p>
        )}
        {state.status === "loaded" && allEntries.length === 0 && (
          <p className="lede">
            Ще немає жодної статті. Перетворіть завершену лексему на статтю на
            вкладці «Сторінки та слова».
          </p>
        )}
        {state.status === "loaded" && allEntries.length > 0 && (
          <div className="grid gap-2">
            <p className="m-0 text-[0.82rem] text-muted-foreground tabular-nums">
              {visible.length === allEntries.length
                ? `${allEntries.length} статей`
                : `${visible.length} з ${allEntries.length}`}
            </p>
            <EntriesTable entries={visible} />
          </div>
        )}
      </div>
    </>
  );
}

function EntriesTable({ entries }: { entries: EntrySummaryResponse[] }) {
  if (entries.length === 0) {
    return (
      <p className="lede">За цим фільтром чи запитом статей не знайдено.</p>
    );
  }
  return (
    <Table className={cn(COMPACT, "max-w-3xl")}>
      <caption className="sr-only">Статті словника</caption>
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Заголовне слово</TableHead>
          <TableHead scope="col">Статус</TableHead>
          <TableHead scope="col" className="text-right">
            Полів
          </TableHead>
          <TableHead scope="col">Оновлено</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry) => (
          <TableRow key={entry.id}>
            <TableCell className="font-[650] [overflow-wrap:anywhere]">
              <Link to={`/entries/${entry.id}`} className="text-primary">
                {entry.headword}
              </Link>
            </TableCell>
            <TableCell>
              <Badge variant={ENTRY_STATUS_VARIANT[entry.status]}>
                {ENTRY_STATUS_LABELS[entry.status]}
              </Badge>
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {entry.field_count}
            </TableCell>
            <TableCell className="text-muted-foreground tabular-nums">
              {formatDate(entry.updated_at)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function EntriesListPage() {
  const { dictionaryId } = useParams<{ dictionaryId: string }>();

  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return <EntriesWorkspace dictionaryId={dictionaryId} />;
}
