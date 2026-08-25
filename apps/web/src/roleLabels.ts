import type { Role } from "./api";

export const ASSIGNABLE_ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: "editor", label: "Редактор" },
  { value: "reviewer", label: "Рецензент" },
  { value: "viewer", label: "Переглядач" },
];

export const ROLE_LABELS: Record<Role, string> = {
  owner: "Власник",
  editor: "Редактор",
  reviewer: "Рецензент",
  viewer: "Переглядач",
};
