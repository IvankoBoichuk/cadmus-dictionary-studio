import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/lib/utils";

import { useDictionaryContext } from "./dictionaryContext";

const SETTINGS_TABS = [
  { to: "metadata", label: "Метадані" },
  { to: "page-ranges", label: "Діапазони сторінок" },
  { to: "abbreviations", label: "Скорочення" },
  { to: "settlements", label: "Географічні мітки" },
  { to: "article-schema", label: "Схема статті" },
  { to: "members", label: "Учасники" },
] as const;

/** Secondary nav for `/dictionaries/:id/settings/*`; forwards the dictionary
 * context from `DictionaryLayout` to the leaf pages. */
export function DictionarySettingsLayout() {
  const context = useDictionaryContext();

  return (
    <div className="grid gap-6 lg:grid-cols-[13rem_minmax(0,1fr)] lg:items-start">
      <nav
        className="flex flex-wrap gap-1 lg:flex-col"
        aria-label="Налаштування словника"
      >
        {SETTINGS_TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              cn(
                "flex min-h-[2.5rem] items-center rounded-md px-3 text-[0.9rem] font-[650] no-underline",
                isActive
                  ? "bg-secondary text-secondary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <div className="min-w-0">
        <Outlet context={context} />
      </div>
    </div>
  );
}
