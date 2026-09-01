import type { ReferenceRelationType } from "./api";

/** Semantic relation between a Cadmus entry and a VESUM reference lemma (ADR-0009). */
export const RELATION_TYPE_LABELS: Record<ReferenceRelationType, string> = {
  standard_equivalent: "Літературний відповідник",
  synonym: "Синонім",
  approximate_equivalent: "Приблизний відповідник",
  hypernym: "Гіперонім",
  related: "Пов'язана лема",
};

/** Order used for the relation-type picker. */
export const RELATION_TYPE_ORDER: ReferenceRelationType[] = [
  "standard_equivalent",
  "synonym",
  "approximate_equivalent",
  "hypernym",
  "related",
];

/** Common VESUM parts of speech; unknown codes fall back to the raw value. */
const PART_OF_SPEECH_LABELS: Record<string, string> = {
  noun: "іменник",
  verb: "дієслово",
  adj: "прикметник",
  adjp: "дієприкметник",
  adv: "прислівник",
  advp: "дієприслівник",
  numr: "числівник",
  pron: "займенник",
  prep: "прийменник",
  conj: "сполучник",
  part: "частка",
  excl: "вигук",
  onomat: "звуконаслідування",
  noninfl: "невідмінюване",
};

export function partOfSpeechLabel(pos: string): string {
  return PART_OF_SPEECH_LABELS[pos] ?? pos;
}
