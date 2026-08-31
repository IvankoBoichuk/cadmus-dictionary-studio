import type { ContributorRole, LegalStatus } from "./api";

export const LEGAL_STATUS_OPTIONS: { value: LegalStatus; label: string }[] = [
  { value: "public_domain", label: "Суспільне надбання" },
  { value: "licensed", label: "За ліцензією" },
  { value: "permission_granted", label: "Дозвіл отримано" },
  { value: "restricted", label: "Обмежений доступ" },
  { value: "unknown", label: "Невідомо" },
];

export const LEGAL_STATUS_LABELS: Record<LegalStatus, string> =
  Object.fromEntries(
    LEGAL_STATUS_OPTIONS.map((option) => [option.value, option.label]),
  ) as Record<LegalStatus, string>;

export const CONTRIBUTOR_ROLE_OPTIONS: { value: ContributorRole; label: string }[] =
  [
    { value: "compiler", label: "Укладач(ка)" },
    { value: "author", label: "Автор(ка)" },
  ];

export const CONTRIBUTOR_ROLE_LABELS: Record<ContributorRole, string> =
  Object.fromEntries(
    CONTRIBUTOR_ROLE_OPTIONS.map((option) => [option.value, option.label]),
  ) as Record<ContributorRole, string>;
