import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";

import type { ReferenceLemmaResponse } from "../api";
import { partOfSpeechLabel } from "../referenceLabels";

/**
 * One reference lemma, shared by the lexicon browser and the entry's
 * link list. When the API matched an inflected word form rather than the
 * headword (`match_type === "word_form"`), the matched form and its raw
 * VESUM morphology are shown so the editor can judge the fit.
 */
export function ReferenceLemmaCard({
  lemma,
  action,
}: {
  lemma: ReferenceLemmaResponse;
  action?: ReactNode;
}) {
  const matchedByForm =
    lemma.match_type === "word_form" && lemma.matched_form
      ? lemma.matched_form
      : null;

  return (
    <div className="grid gap-1.5 rounded-md border border-border bg-surface p-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="font-serif text-[1.05rem] font-medium [overflow-wrap:anywhere]">
            {lemma.lemma}
          </span>
          <span className="ml-2 text-[0.8rem] text-muted-foreground">
            {partOfSpeechLabel(lemma.part_of_speech)}
          </span>
        </div>
        {action}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <Badge variant={lemma.is_standard ? "secondary" : "warning"}>
          {lemma.is_standard ? "нормативна" : "ненормативна"}
        </Badge>
        {lemma.key_tags.map((tag) => (
          <Badge key={tag} variant="info" className="font-mono">
            {tag}
          </Badge>
        ))}
      </div>

      {matchedByForm && (
        <p className="m-0 text-[0.8rem] text-muted-foreground [overflow-wrap:anywhere]">
          Збіг за словоформою <span className="font-medium">{matchedByForm}</span>
          {lemma.matched_form_morphology ? (
            <span className="ml-1 font-mono text-[0.75rem]">
              {lemma.matched_form_morphology}
            </span>
          ) : null}
        </p>
      )}
    </div>
  );
}
