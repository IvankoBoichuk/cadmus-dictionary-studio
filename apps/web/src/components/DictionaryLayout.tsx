import { useState } from "react";
import { NavLink, Navigate, Outlet, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import { dictionaryThumbnailUrl, type DictionaryResponse } from "../api";
import {
  DICTIONARY_STATUS_BADGE_VARIANT,
  DICTIONARY_STATUS_LABELS,
} from "../dictionaryStatusLabels";
import { useDictionary } from "../hooks/useDictionary";
import type { DictionaryContext } from "./dictionaryContext";

const TABS = [
  { to: ".", label: "Огляд", end: true },
  { to: "pages", label: "Сторінки та слова", end: false },
  { to: "settings", label: "Налаштування", end: false },
] as const;

/** Sub-shell for every `/dictionaries/:id/*` screen: loads the dictionary once,
 * shows a sticky header (cover + title + status) and the primary tabs. */
export function DictionaryLayout() {
  const { dictionaryId } = useParams<{ dictionaryId: string }>();
  const load = useDictionary(dictionaryId ?? "");
  const [override, setOverride] = useState<DictionaryResponse | null>(null);

  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  const dictionary =
    override ?? (load.status === "loaded" ? load.dictionary : null);

  if (load.status === "error") {
    return (
      <p className="form-error" role="alert">
        {load.message}
      </p>
    );
  }
  if (!dictionary) {
    return <p role="status">Завантажуємо словник…</p>;
  }

  return (
    <>
      <header className="sticky top-0 z-20 -mx-[clamp(1rem,4vw,2.5rem)] -mt-[clamp(2rem,6vw,3.5rem)] mb-6 bg-background/90 px-[clamp(1rem,4vw,2.5rem)] pt-3 backdrop-blur-sm">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <img
            src={dictionaryThumbnailUrl(dictionary.id)}
            alt=""
            width={36}
            height={48}
            loading="lazy"
            className="h-12 w-9 shrink-0 rounded-sm border border-border bg-secondary object-cover object-top"
          />
          <div className="min-w-0 flex-1">
            <p className="text-[0.7rem] font-[750] tracking-[0.12em] text-muted-foreground uppercase">
              Словник
            </p>
            <h1
              id="dictionary-title"
              className="mt-0.5 mb-0 max-w-none truncate font-serif text-[1.4rem] leading-tight font-medium"
            >
              {dictionary.title ?? "Без назви"}
            </h1>
          </div>
          <Badge
            size="lg"
            variant={DICTIONARY_STATUS_BADGE_VARIANT[dictionary.status]}
          >
            {DICTIONARY_STATUS_LABELS[dictionary.status]}
          </Badge>
          <div
            id="dictionary-header-actions"
            className="flex items-center gap-3 empty:hidden"
          />
        </div>
        <nav
          className="flex gap-1 overflow-x-auto border-b border-border pt-3"
          aria-label="Розділи словника"
        >
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                cn(
                  "-mb-px flex min-h-[2.75rem] items-center border-b-2 px-4 text-[0.95rem] font-[650] whitespace-nowrap no-underline",
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <Outlet
        context={
          { dictionary, onUpdated: setOverride } satisfies DictionaryContext
        }
      />
    </>
  );
}
