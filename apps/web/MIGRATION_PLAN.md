# План міграції стилів: CSS → Tailwind CSS v4 + shadcn/ui

> Область міграції: **лише `apps/web`** (React + TS + Vite). FastAPI backend не чіпаємо.
> Пакетний менеджер: **Bun** (`bunx`, не `npx`).
> Статус: **Кроки 1–2 ✅. Крок 3 (примітиви): `Button`, Link-кнопки, `Input`+`Label`, `Textarea`, `Checkbox` ✅; `Select` — компонент + non-Formik selectʼи ✅ (Formik-selectʼи → з RHF).** Tailwind v4 + shadcn/ui; старий CSS ізольовано в `@layer legacy`. build + type-check + lint + 205 тестів — зелені. `Card` ✅ (+ `.status-card`/`.dictionary-card`; `.auth-card` → з auth-RHF). `.form-section` → `@utility` ✅. `Badge` ✅. `Progress` ✅. `Table` ✅. `sr-only` ✅. Layout/оболонка ✅. Компоненти (Крок 3): `ScanProgressBar` ✅, `PageRangeEditor` ✅, `DictionaryReadiness` ✅, `DictionarySourceUpload` (file-summary) ✅, `ApiStatus` ✅, `SettlementSearchCombobox` ✅, `DictionaryPageViewer` ✅, `LexemeList` ✅, `LexemeCanvas` ✅, `EntryFragmentCrop` ✅, `AbbreviationsTable`/`SettlementsTable` (`.table-actions` + мертвий `.badge*`/`.*-table*` CSS) ✅, `DictionaryMetadataForm`/`AbbreviationForm` (`.contributor-*`, `.language-grid`, `.missing-fields` + мертві `.*-button`/`.progress-*`/`.checkbox-field`/`.language-option`) ✅. **Фаза «компоненти по одному» ✅. Блок форм (Formik → react-hook-form + zod + shadcn `Form`) ✅** — усі 7 Formik-хуків + компоненти/сторінки/тести; `formik` прибрано; додано `ui/form.tsx`; Formik-selectʼи → Radix `Select`. **Блок сторінок ✅** — auth-сторінки (`.auth-*`/`.result-message*`/`.oauth-*`/`.google-oauth-*` → `@utility` `auth-page`/`auth-card` + inline-утиліти), `DictionariesList` (`.dictionary-grid`/`.dictionary-card*`/`.dictionary-thumbnail*`), `ArticleSchemaPage`/`EntryDetailPage` (`.schema-field-*`/`.entry-field-*` — безкласові, preflight-регрес виправлено); спільні `.dictionary-form`/`.section-hint`/`.form-actions`/`.form-field`/`.field-hint`/`.field-error`/`.form-error` → `@utility`. **Тепер `grep` по `src/` не знаходить жодного кастомного класу поза `@utility`-набором.** У `@layer legacy` лишилось тільки: глоб. reset + типографіка + 3 descendant-твіки (`.auth-card h1`, `.form-section h2`, `.form-field label`/`input`). Далі — **Крок 4** (глоб. `button {}` reset — потрібне рішення користувача; глоб. `h1`; безкласові поля в `EntryDetailPage`; ручна візуальна перевірка). type-check/lint/build/205-тестів — зелені. CSS-бандл 40.7 kB (було ~44.8).
>
> **Підтверджені рішення (2026-08-28):**
> 1. Файл плану лишається в `apps/web/`.
> 2. Нативні `<select>` → мігрувати на shadcn/Radix `Select`.
> 3. **Formik → `react-hook-form` + shadcn `Form` + `zod`** — повна міграція всіх ~20 хуків форм та їхніх тестів.
> 4. Dark mode не додаємо (застосунок light-only).
> 5. Playwright **не** ставимо — ручні скріншоти before/after + наявні Vitest-тести.
> 6. Токени-дублікати зводимо до однієї пари fg/bg на кожну роль (див. §2).

---

## 1. Інвентаризація стилів (Крок 0)

### 1.1. Файли стилів

| Файл | Рядків | Опис |
|------|--------|------|
| `apps/web/src/styles.css` | 1118 | **Єдиний** глобальний стиль-файл. Імпортується один раз у `src/main.tsx`. |

- Немає CSS Modules, немає SCSS/SASS/LESS, немає component-scoped стилів.
- Немає `styled-components` / `emotion` / інших CSS-in-JS.
- Tailwind **не встановлений**. Playwright **не встановлений** (тести — Vitest + Testing Library).
- Уся стилізація — глобальні класи + селектори по тегах (`button`, `a`, `h1`, `input` всередині `.form-field` тощо).

### 1.2. Кастомні CSS-змінні

**Явних `--custom-property` у коді немає.** Усі значення — «магічні» hex/rem-літерали, розкидані по `styles.css`.
Нижче — токени, які треба **витягти з літералів** у блок `@theme`.

#### Кольори

| Роль | Значення | Де вживається |
|------|----------|---------------|
| `--color-background` | `#f3f5ef` | body, `theme-color` в `index.html` |
| `--color-foreground` | `#1d2925` | основний текст, `.skip-link` bg |
| `--color-primary` | `#245847` | кнопки, `.primary-link`, акценти, focus-border інпутів |
| `--color-primary-foreground` | `#ffffff` | текст на кнопках |
| `--color-primary-strong` | `#33443d` | заголовки таблиць, `.file-summary` |
| `--color-muted-foreground` | `#50605a` / `#61726b` / `#527064` | `.lede`, підказки, `.eyebrow` (**3 близькі відтінки — потребує узгодження**) |
| `--color-border` | `#d6dbd2` | усі рамки карток/таблиць |
| `--color-input` | `#9aa7a1` | рамка інпутів |
| `--color-ring` | `#d58d36` (помаранчевий) | `:focus-visible` outline на button/a |
| `--color-ring-subtle` | `#dcebe5` | `:focus-visible` outline на інпутах |
| `--color-surface` | `#ffffff` | картки, інпути |
| `--color-secondary` | `#eaf1ec` | `.secondary-button`, `.icon-button`, badge-success bg |
| `--color-secondary-hover` | `#f4f7f4` | `.google-oauth-button:hover` |
| `--color-track` | `#e3e8e0` | `.progress-track` |
| `--color-success-fg` / `--color-success-bg` | `#175c3a` / `#ddf3e8` (також `#158052`, `#17663f`, `#dff3e9`) | статуси, badge (**кілька майже однакових пар — узгодити**) |
| `--color-warning-fg` / `--color-warning-bg` | `#7a5b12` / `#fbf1da` | `.missing-fields`, `.badge--warning`, `.status-badge--draft` |
| `--color-info-fg` / `--color-info-bg` | `#1d5c8a` / `#e6f0f7` | `.badge--suggested`, `.badge--status` |
| `--color-danger-fg` / `--color-danger-bg` | `#9a3024` / `#fbe9e6` (також `#8a2e22`, `#b43c2d`) | помилки, `.danger-button` |
| `--color-selected` | `#b91c1c` | вибраний lexeme-box / list-item (червоний) |
| `--color-lexeme` | `#d97706` + `rgb(217 119 6 / …)` | рамки боксів на canvas |
| `--color-lexeme-suggestion` | `#2563eb` + `rgb(37 99 235 / …)` | пунктирні бокси-підказки OCR |
| `--color-header-bg` | `rgb(255 255 255 / 72%)` | `.site-header` (напівпрозорий) |
| `--color-muted-dot` | `#8e9692` | `.status-dot` (нейтральний) |
| card shadow | `0 1rem 3rem rgb(35 57 49 / 8%)` | `.auth-card`, `.status-card`, `.dictionary-card` |

#### Шрифти

| Токен | Значення |
|-------|----------|
| `--font-sans` | `Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif` |
| `--font-serif` | `Georgia, "Times New Roman", serif` (бренд, `h1`, `h2`, `h3`) |

#### Радіуси

| Токен | Значення | Вживання |
|-------|----------|----------|
| `--radius-pill` | `999px` | кнопки, badges, progress-track |
| `--radius-xl` | `1.25rem` | `.auth-card` |
| `--radius-lg` | `1rem` | картки, `.form-section` |
| `--radius-md` | `0.75rem` | `.page-viewer-image`, `.entry-fragment-crop` |
| `--radius-sm` | `0.5rem–0.55rem` | інпути |
| `--radius-xs` | `0.35rem–0.4rem` | дрібні бейджі сторінок скану |

#### Spacing / інше

- Spacing — переважно rem-літерали + `clamp()` для флюїдних відступів (`clamp(3rem, 9vw, 7rem)` тощо). Базова шкала Tailwind підходить; флюїдні значення лишаємо як утиліти з довільним значенням `p-[clamp(...)]` або окремі токени `--spacing-*`.
- Focus outline: `3px solid` + `outline-offset: 3px`.
- Переходи: `filter .12s ease` (кнопки), `transform .2s ease` (progress bar).
- `font-variant-numeric: tabular-nums` — лічильники/номери сторінок.

#### Брейкпоінти (кастомні media-queries)

| Значення | Де |
|----------|-----|
| `max-width: 38rem` | `.status-card` → 1 колонка |
| `max-width: 768px` | `.page-viewer-body` → 1 колонка |
| `prefers-reduced-motion: reduce` | глобальне вимкнення анімацій |
| `prefers-color-scheme` | **не використовується** — застосунок light-only (`color-scheme: light`) |

### 1.3. Кастомні UI-компоненти → кандидати на shadcn/ui

| Поточний патерн (клас/тег) | shadcn/ui еквівалент | Складність / застереження |
|---|---|---|
| `<button>` (глоб.), `.secondary-button`, `.danger-button`, `.icon-button` | **`Button`** (`variant`: default / secondary / destructive / ghost / outline; `size`: default / icon) | Глобальний селектор `button {}` впливає на все — прибирати лише після заміни **всіх** місць. |
| `.primary-link`, `.secondary-link` (посилання-як-кнопки) | **`Button` + `asChild`** з `<Link>` або `buttonVariants()` | — |
| `.form-field input` | **`Input`** + **`Label`** | Formik `getFieldProps` сумісний (звичайний `<input>`). |
| `.form-field textarea` | **`Textarea`** | — |
| `.form-field select` + всі нативні `<select>` (8 місць) | **`Select`** (Radix, shadcn) | Дріт `value/onValueChange` через `Controller` з react-hook-form. |
| `.checkbox-field`, `.language-option` | **`Checkbox`** + `Label` | Дріт через `Controller` з react-hook-form. |
| `.auth-card`, `.status-card`, `.form-section`, `.dictionary-card` | **`Card`** (`Card` / `CardHeader` / `CardTitle` / `CardContent` / `CardFooter`) | — |
| `.badge`, `.badge--*`, `.status-badge--*` | **`Badge`** (`variant`: default / secondary / destructive / outline + кастомні success/warning/info) | Треба додати кастомні варіанти. |
| `.progress-track` + `.progress-bar`, `.scan-progress` | **`Progress`** | `.scan-progress-pages` (сітка плиток) лишається кастомною. |
| `.abbreviation-table`, `.settlement-table`, `.member-table`, `.table-wrapper` | **`Table`** (`Table` / `TableHeader` / `TableRow` / `TableHead` / `TableBody` / `TableCell`) | 3 таблиці з ідентичними стилями — уніфікувати. |
| `.skip-link`, `.visually-hidden` | утиліта `sr-only`; `.skip-link` лишається кастомним хелпером | — |
| `.field-error`, `.form-error` | **`Form`** (shadcn: `Form` / `FormField` / `FormItem` / `FormLabel` / `FormControl` / `FormMessage`) на `react-hook-form` + `zod` | Повна заміна Formik. Валідація існуючих `useXxxForm` переноситься в `zod`-схеми. |
| `SettlementSearchCombobox` | Це не combobox: `<input>` + 3 нативні `<select>` + `<ul>` результатів. Справжній shadcn Combobox (`Command` + `Popover`) — **опційно, поза базовою областю**. | Поки що — просто утиліти. |
| `.site-header`, `.brand`, `.hero`, `.eyebrow`, `.lede` | Немає еквіваленту — переписуємо на утиліти. | — |
| `.lexeme-canvas`, `.lexeme-box--*`, `.lexeme-resize-handle--*`, `.entry-fragment-*` | Немає еквіваленту — переписуємо на утиліти (багато `position: absolute`, курсори resize). | Найскладніший компонент. Зберегти піксель-в-піксель. |

**Діалогів / модалок / dropdown-меню / popover / tooltip у проєкті немає** — відповідні пакети shadcn не потрібні.

### 1.4. Мертві / безстильові класи (прибрати принагідно)

- `schema-field-tree`, `schema-field-name`, `entry-field-list`, `entry-field-row` — вживаються в TSX, **правил у `styles.css` немає**.

---

## 2. Пропонований `@theme` (Крок 1, чернетка)

```css
@import "tailwindcss";
@plugin "tailwindcss-animate"; /* потрібен для shadcn */

@theme {
  --font-sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-serif: Georgia, "Times New Roman", serif;

  --color-background: #f3f5ef;
  --color-foreground: #1d2925;
  --color-surface: #ffffff;
  --color-primary: #245847;
  --color-primary-foreground: #ffffff;
  --color-secondary: #eaf1ec;
  --color-secondary-foreground: #245847;
  --color-muted-foreground: #61726b;
  --color-border: #d6dbd2;
  --color-input: #9aa7a1;
  --color-ring: #d58d36;

  --color-success-foreground: #175c3a;
  --color-success:            #ddf3e8;
  --color-warning-foreground: #7a5b12;
  --color-warning:            #fbf1da;
  --color-info-foreground:    #1d5c8a;
  --color-info:               #e6f0f7;
  --color-destructive-foreground: #9a3024;
  --color-destructive:        #fbe9e6;

  --radius: 1rem;

  --shadow-card: 0 1rem 3rem rgb(35 57 49 / 8%);
}
```

> `shadcn init` згенерує власні `--background/--foreground/...` у `:root`. На Кроці 2 узгодити: **не дублювати** — привести shadcn-змінні до значень вище, лишити один набір.

---

## 3. Чекліст міграції

### Крок 1 — Фундамент Tailwind v4 ✅

- [x] Встановити `tailwindcss` + `@tailwindcss/vite` (`bun add -D`) — v4.3.3
- [x] Підключити плагін `@tailwindcss/vite` у `vite.config.ts`
- [x] `src/styles.css`: додано `@import "tailwindcss";` (нових `@tailwind` директив тут не було)
- [x] Перенесено токени з §2 у блок `@theme`
- [ ] `@plugin` для анімацій shadcn — **відкладено на Крок 2** (shadcn init сам додасть `tw-animate-css`)
- [x] `bun run build` — зелено; `bun run test` — 205/205; dev-сервер стартує без помилок
- [x] Старий CSS лишається у `styles.css` (нижче `@theme`) — прибиратимемо порціями

### Крок 2 — Ініціалізація shadcn/ui ✅

- [x] Path alias `@/*` → `./src/*` у `tsconfig.json`, `tsconfig.app.json`, `vite.config.ts` (`resolve.alias`)
- [x] `components.json` створено вручну (інтерактивний `shadcn init` не автоматизується в цьому середовищі — зациклюється на виборі preset). style `new-york`, base `radix`, `iconLibrary: lucide`, `css: src/styles.css`, `cssVariables: true`
- [x] `src/lib/utils.ts` (`cn()` на `clsx` + `tailwind-merge`)
- [x] Deps: `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `radix-ui`; dev: `tw-animate-css`
- [x] `src/styles.css`: `@import "tw-animate-css";`, `@custom-variant dark`, `:root` з shadcn-токенами → значення Cadmus, `@theme inline` (мапінг + `--radius-*`), `@layer base { * { @apply border-border outline-ring/50 } }`
- [x] Dark mode: `.dark`-блок не створюється; `@custom-variant dark` лишено, щоб `dark:` класи shadcn не ламали збірку
- [x] `bunx shadcn@latest add button` — працює (створив `src/components/ui/button.tsx`)
- [ ] `bun add react-hook-form @hookform/resolvers zod` — **відкладено на початок блоку «Форми»** у Кроці 3

### Крок 3 — Спільні примітиви (мігрувати ПЕРШИМИ, по одному)

- [x] `Button` ✅ — `src/components/ui/button.tsx` адаптовано під вигляд Cadmus (pill-радіус, `#245847`, hover `brightness(.93)`, focus `3px solid #d58d36` offset 3px, disabled `opacity .68`). Відповідники: `.secondary-button`→`variant="secondary"`, `.danger-button`→`variant="danger"` (нова м'яка variant, НЕ shadcn `destructive`), `.icon-button`→`variant="secondary" size="icon"`, компактні кнопки `.lexeme-list-actions`→`size="sm"`. **72 конверсій у 26 файлах.** Пропущено: `<button className={dynamic}>` (`.scan-progress-page`), `.primary-link`/`.secondary-link` на `<button>` (наступний пункт). `styles.css`: увесь старий CSS обгорнуто в `@layer legacy` (нижче за `@layer utilities`), тож utility-класи `<Button>` перекривають старі правила; сам старий CSS (`button{}`, `.secondary-button`, ...) лишається до Кроку 4. Перевірено: type-check ✅, lint ✅ (1 давнє warning shadcn), build ✅, 205/205 тестів ✅.
- [x] Link-кнопки ✅ — `.primary-link` → `<Button asChild className="mt-4 px-[1.1rem] py-3"><Link/></Button>` (padding `.75rem 1.1rem` + `margin-top:1rem` збережено; у `.header-actions` `mt-4` не додається). `.secondary-link` (не кнопка, а текст-лінк) → inline utility `ml-4 inline-block font-[650] text-primary hover:underline` прямо на `<Link>`/`<a>` (`ml-4` прибрано в `.header-actions` та `.dictionary-card-actions`, де старе правило його занулювало). `<button className="primary-link">` у `LexemeCanvas` → `<Button className="mt-4 px-[1.1rem] py-3">`. Зачеплено 7 файлів (AuthActions, DashboardPage, DictionariesList, DictionaryFormPage×6, AbbreviationsPage×2, SettlementsPage×2, LexemeCanvas). Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅. **Прим.:** у `LexemeCanvas` `.primary-link` submit-кнопка всередині flex `.form-actions` мала `margin-top:1rem` → лишається зміщеною на 1rem нижче сусідньої «Скасувати» (давній артефакт; за бажання прибрати `mt-4`).
- [x] `Input` + `Label` ✅ — `bunx shadcn add input label`; обидва адаптовано під `.form-field`: `Input` = border `#9aa7a1` (`--input`), radius `.55rem`, `min-h-2.9rem`, padding `.65rem .8rem`, `bg-surface`, шрифт успадкований, focus → border `--primary` + `outline:3px solid var(--color-ring-subtle)` (#dcebe5), `aria-invalid:border-destructive` (зведено з давнього `#b43c2d`, рішення №3); `Label` = `font-bold`, розмір успадкований (без `text-sm`). Замінено **лише `<input>` прямий нащадок `.form-field`** (+ їх видимі `<label>`, у т.ч. для сусідніх `<select>`/`<textarea>` — для консистентності) у 10 файлах: LoginPage, RegisterPage, ForgotPasswordPage, ResetPasswordPage, SettlementForm, SettlementSearchCombobox, AbbreviationImportPanel, SettlementImportPanel, AbbreviationForm, DictionaryMetadataForm. Пропущено (свій стиль / інший пункт): `.contributor-row`/`.page-range-row`/`.lexeme-form` інпути, `<input type="checkbox">` у `.checkbox-field`/`.language-option`, sr-only `<label className="visually-hidden">`, безкласові інпути `AddFieldForm` у `EntryDetailPage` (там немає `.form-field` — піде з пунктом компонента). Formik `getFieldProps` сумісний (звичайний `<input>`). Перевірено: type-check ✅, lint ✅, build ✅ (CSS 33.8 kB), 205/205 ✅.
- [x] `Textarea` ✅ — `src/components/ui/textarea.tsx` написано вручну як `Input` + `min-h-[5rem]` + `resize-y` (= старе `.form-field textarea`). Замінено 5 `<textarea>` у 3 файлах (SettlementForm, AbbreviationForm, DictionaryMetadataForm — усі вже з Input/Label). Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅ (флейк `EntryDetailPage.test.tsx` при паралельному прогоні — давній, не пов'язаний зі зміною; ізольовано і на повторі зелено).
- [~] `Select` (shadcn/Radix) — компонент готовий + мігровані selectʼи БЕЗ Formik. ✅ Зроблено:
  - `bunx shadcn add select`; `SelectTrigger` адаптовано під `.form-field select` (рамка `--input`, radius `.55rem`, `min-h-2.9rem` / `sm` → `2.4rem`, `bg-surface`, `text-foreground` (обов'язково — тригер це `<button>`, ще ловить старе `button{color:#fff}`), focus як в `Input`). `SelectContent` — `position="item-aligned"` (як нативний select).
  - `src/test/setup.ts`: додано poly-стаби `hasPointerCapture` / `setPointerCapture` / `releasePointerCapture` для Radix у jsdom; додано dev-залежність `@testing-library/user-event` (перший ужиток у сумі — тести Radix потребують click-взаємодії).
  - Мігровано: `ProjectMemberForm` (role + заодно `.form-field` email → `Input`/`Label`), `ProjectMembersTable` (role, `size="sm"`; тест ролі переписано на `userEvent`), `SettlementSearchCombobox` (3 гео-select; «усі …» кодується сентинелом `__all__`, бо Radix не приймає порожнє значення).
  - Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅. **Прим.:** `@radix-ui/react-select` додав ~90 kB (31 kB gzip) до JS-бандла → Vite тепер показує advisory >500 kB (не помилка; code-split — окреме питання).
  - **Відкладено** (біндинг через `Controller` при переписі на RHF): `AbbreviationForm` (category, language_code), `DictionaryMetadataForm` (legal_status). **Відкладено на пункт компонента:** `DictionaryMetadataForm` (contributor role), `EntryDetailPage` (fragment / schema-path / manual-role / field-role — там немає `.form-field`, зараз browser-default).
- [x] `Checkbox` ✅ — `bunx shadcn add checkbox`; адаптовано: `size-4`, `rounded-[4px]`, `border-input`, `bg-surface p-0` (обов'язково — Root це `<button>`, ще ловить `button{background:#245847;padding:.7rem 1rem}` з `@layer legacy`), checked → `bg-primary`, focus як в `Input`. Структуру `<label><input/>текст</label>` замінено на shadcn-ідіому `<div class="flex items-center gap-2"><Checkbox id/><Label htmlFor/></div>` (`<label for>` валідно і для `<button>`, тож клік по тексту працює). Мігровано (обидва Formik, глью тривіальний, не відкладав): `AbbreviationForm` (`unresolved` → `onCheckedChange` + `setFieldValue`), `DictionaryMetadataForm` (мови → `toggleLanguage`). `.language-option` було `font-weight:600` → `<Label className="font-semibold">`; `.checkbox-field` фактично рендериться 700 (`.form-field label` перебивав) → плейн `<Label>`. `src/test/setup.ts`: додано стаб `ResizeObserver` (Radix Checkbox викликає `useSize` на маунті). Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅.
- [ ] `Form` (shadcn, на react-hook-form) — `FormField/FormItem/FormLabel/FormControl/FormMessage`; замінює `.form-field`, `.field-error`, `.form-error`
- [~] `Card` — компонент + `.status-card` / `.dictionary-card` ✅:
  - `bunx shadcn add card`; базу зведено до «поверхні» Cadmus (`rounded-lg border bg-card text-card-foreground shadow-card`), опінійований layout shadcn (`flex/gap-6/py-6`) прибрано — його задає місце вжитку. Додано `asChild` (щоб лишити `<section>` / `<li>`). Сабкомпоненти (`CardHeader/Title/Content/...`) лишено на майбутнє.
  - `ApiStatus` (`.status-card`) → `<Card asChild><section>` + утиліти для grid-layout (`grid-cols-[minmax(8rem,1fr)_auto_auto] gap-6 p-6 max-[38rem]:grid-cols-[1fr]`), `h2` → `text-xl mb-0`, retry-кнопка → `max-[38rem]:justify-self-start`.
  - `DictionariesList` (`.dictionary-card`) → `<Card asChild className="flex flex-col overflow-hidden"><li>`. Внутрішні `.dictionary-card-body` / `-actions` лишились (окремі класи, підуть із пунктом сторінки).
  - Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅.
  - **Відкладено `.auth-card`** (11 місць `<section>` + описові правила `.auth-card h1/form/button`, `.auth-card--result` — природно робити разом з переписом auth-сторінок на RHF).
- [x] `.form-section` → Tailwind `@utility` ✅ — у `styles.css` додано `@utility form-section { @apply grid gap-[1.1rem] rounded-lg border bg-card p-[clamp(1.25rem,4vw,2rem)] }` (поза `@layer legacy`); старе правило `.form-section {…}` видалено з legacy; `.form-section h2 { font-size: 1.15rem }` лишено (descendant-твік). **JSX не змінювався** (~30 місць `className="form-section"` працюють як є). Компільований CSS 1:1 зі старим. Перевірено: build ✅, type-check ✅, lint ✅, 205/205 ✅.
- [x] `Badge` ✅ — `bunx shadcn add badge`, переписано на `cva` з двома вимірами: `size` (`default` = `.badge`: `px-2 py-[.15rem] text-[.78rem]` weight 650; `lg` = `.status-badge`: `px-3 py-[.3rem] text-[.85rem]` weight 600) і `variant` на семантичні токени: `info` (=`--status`/`--suggested`, дефолт), `secondary` (=`--ok`/`--confirmed`/`--complete`), `warning` (=`--warning`/`--unresolved`/`.status-badge--draft`), `danger` (=`--error`), `success` (=`.status-badge--configured`). Старе `.badge { margin-left:.5rem }` не в компоненті → `className="ml-2"` на місці. `badgeVariants` не експортую (немає вжитку, зайвий `react-refresh` warning). Мігровано 18 місць у 8 файлах: статичні (ArticleSchemaPage ×5, Settlement/AbbreviationImportPanel ×3+3, AbbreviationsTable ×1, EntryDetailPage ×3) + динамічні через мапу `Record<status, variant>` (SettlementsTable, LexemeList `isComplete ? secondary : info`, DictionaryReadiness `size="lg"`). **Прим.:** `DictionaryStatus "scanned"` не мав CSS-варіанта (рендерився без фону) → тепер `success`. Перевірено: type-check ✅, lint ✅ (те саме 1 давнє warning), build ✅, 205/205 ✅.
- [x] `Progress` ✅ — `bunx shadcn add progress`; адаптовано: трек `h-[0.6rem] rounded-full bg-track`, індикатор `bg-primary transition-transform duration-200` (= старе `.progress-track`/`.progress-bar`). Додано токен `--color-track: #e3e8e0` у `@theme`. Мігровано 2 місця: `DictionarySourceUpload` (аплоад; ручні `role="progressbar"`/`aria-value*` прибрано — Radix додає сам, лишив `aria-label`), `ScanProgressBar` (`<Progress value={percent} />`; `.scan-progress-pages` — сітка плиток — лишилась кастомною). Тести на progressbar-роль/атрибути не було. Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅.
- [x] `Table` ✅ — `bunx shadcn add table`; адаптовано під 3 ідентичні старі таблиці: wrapper `overflow-x-auto overscroll-x-contain`, table `w-full border-collapse`, `TableHead` = `px-3 py-[.6rem] text-left align-top text-[.85rem] font-bold text-primary-strong`, `TableCell` = те саме + `[overflow-wrap:anywhere]`, `TableRow` = `border-b` (без `[&_tr:last-child]:border-0` — старий лишав рамку й на останньому рядку), **без** row-hover (у старому не було). Мігровано 5 таблиць у 5 файлах (AbbreviationsTable, SettlementsTable, ProjectMembersTable, Abbreviation/SettlementImportPanel): `<div className="table-wrapper"><table className="X-table">` → `<Table>` (wrapper всередині компонента), `thead/tbody/tr/th/td` → `TableHeader/Body/Row/Head/Cell`; `<caption className="visually-hidden">` лишено. Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅.
- [x] `sr-only` ✅ — `.visually-hidden` (ідентична до вбудованого Tailwind `sr-only`) → `className="visually-hidden"` замінено на `"sr-only"` у 17 місцях / 12 файлів; правило `.visually-hidden {…}` видалено зі `styles.css`. `<caption>` у таблицях теж на `sr-only`. Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅.

### Крок 3 — Layout / оболонка

- [x] `App.tsx` оболонка ✅ — одноразові класи → інлайн utility: `.app-shell`→`min-h-screen`, `.skip-link`→`fixed top-4 left-4 z-[2] -translate-y-[180%] bg-foreground px-4 py-3 text-white focus:translate-y-0`, `.site-header`→`flex min-h-[4.5rem] items-center border-b bg-white/[0.72] px-[6vw]`, `.brand`→`font-serif text-[1.45rem] font-bold tracking-[0.02em] no-underline`. `AuthActions.tsx`: `.header-actions`→`ml-auto flex items-center gap-4` (×2), `.logout-error`→`m-0 max-w-[28rem] text-[0.9rem] text-destructive` (колір зведено #8a2e22→--destructive). Правила видалено зі `styles.css`.
- [x] Спільні layout-класи → `@utility` ✅ — `.page`, `.hero`, `.lede`, `.eyebrow`, `.status-label` винесено в `@utility` (styles.css, поза legacy), старі правила видалено. JSX не змінювався (класи ті самі). Кольори `.eyebrow`/`.status-label` (#527064) і `.lede` (#50605a) зведено до `--muted-foreground` (#61726b) — рішення №2. Глобальні `h1/h2/h3`-правила лишились (окрема типографіка, Крок 4). Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅.

### Крок 3 — Форми: Formik → react-hook-form + zod (по одній, з перевіркою та diff)

> Кожен пункт: переписати хук `useXxxForm` на `useForm` + `zodResolver`, перенести правила валідації у `zod`-схему, оновити компонент на shadcn `Form`, оновити відповідний `*.test.tsx`.

**Інфраструктура:** `bun add react-hook-form @hookform/resolvers zod` (RHF 7.87, zod 4.5); `formik` **прибрано** з `package.json`. Додано `src/components/ui/form.tsx` — стандартний shadcn `Form`/`FormField`/`FormItem`/`FormLabel`/`FormControl`/`FormDescription`/`FormMessage`, адаптований під `radix-ui` (єдиний пакет) + токени зі `styles.css` (`FormItem` = `grid gap-[0.45rem]` = старий `.form-field`; `FormMessage` = `text-destructive` #9a3024 = старий `.field-error`; `FormDescription` = `text-muted-foreground` #61726b = старий `.field-hint`). **Прим.:** `import * as z from "zod"` (не `import { z }`) — Zod 4 re-експортує `z` як namespace-біндинг, і vitest/vite SSR-трансформ на `import { z }` дає `undefined`.

- [x] `hooks/useLoginForm.ts` + `pages/LoginPage.tsx` ✅ — `useForm` + `zodResolver`, `mode: "onTouched"`. Валідація email/пароль → zod-схема. Помилка сабміту (недоступний сервіс / невірні дані) → `form.setError("root")`, рендер `form.formState.errors.root?.message`. `useFocusFirstError(formRef, form.formState.submitCount, form.formState.isSubmitting)`. Поля → `FormField`+`FormControl`+`Input`; `.field-hint` (лінк «Забули пароль?») → `m-0 text-[0.88rem] text-muted-foreground`; `.form-error` (session/google) → `m-0 text-[0.88rem] text-destructive`; `<form className="mt-8 grid gap-5">` (= `.auth-card form`). `.auth-*` shell — лишається (блок сторінок).
- [x] `hooks/useRegistrationForm.ts` + `pages/RegisterPage.tsx` ✅ — zod `.refine` для збігу паролів (`path: ["password_confirmation"]`), API field-errors → `form.setError(field)`, успіх → `useState(message)` + окрема гілка рендеру. `.field-hint` «≥12 символів» → `FormDescription`. `App.test.tsx`: 2 асерти `toHaveAttribute("aria-describedby", "email-error")` → `toHaveAccessibleDescription(...)` (shadcn генерує id-и).
- [x] `hooks/useForgotPasswordForm.ts` + `pages/ForgotPasswordPage.tsx` ✅ — той самий патерн, успіх → `useState(message)`.
- [x] `hooks/useResetPasswordForm.ts` + `pages/ResetPasswordPage.tsx` ✅ — zod `.refine` збіг паролів; `tokenError` → окремий `useState` (гілка `InvalidLinkResult`); API field-errors (`password`/`password_confirmation`) → `setError("new_password"/"new_password_confirmation")`.
- [x] `hooks/useAbbreviationForm.ts` + `components/AbbreviationForm.tsx` ✅ — zod `.superRefine` (обов'язкове скорочення/категорія; повна форма обов'язкова, якщо не «нерозшифроване»); `mode: "onBlur"`. `variants: string[]` → `{ value: string }[]` + `useFieldArray` (append/remove). `editing` reset — `useEffect([editing]) → form.reset(valuesFrom(editing))` (`reset` чистить і `root`-помилку, і `isDirty` — як старий `resetForm`). Помилка сабміту → `form.setError("root")` (не `useState` — інакше `set-state-in-effect` lint-error), рендер `form.formState.errors.root?.message`. `<select>` категорії/мови → shadcn **Radix `Select`** (мова: сентинел `__none__`). `useUnsavedChangesWarning(form.formState.isDirty && !isSubmitting)`. Тест: 2 місця `fireEvent.change(select)` → `userEvent.click(combobox)` + `click(option)`.
- [x] `hooks/useSettlementForm.ts` + `components/SettlementForm.tsx` ✅ — zod `.superRefine` (обов'язкова позначка з оригіналу). `applySuggestion`/`clearSuggestion` → `form.setValue(..., { shouldDirty: true })`. `settlement_id`/`modern_*`/`category` читаються через `form.watch(...)` **у тілі компонента** (не в хуку — `watch` в return хука = `incompatible-library` lint-error). Помилка сабміту → `setError("root")`. Селектів немає — тести без змін.
- [x] `hooks/useDictionaryMetadataForm.ts` + `components/DictionaryMetadataForm.tsx` ✅ — zod `.superRefine` (рік/ISBN через наявні `validatePublicationYear`/`validateIsbn`; умовні `license_type`/`permission_reference`); `mode: "onBlur"`. `contributors` → `useFieldArray` (append/remove/**move**); ім'я/роль per-row через `form.register(\`contributors.${i}.name|role\`)`; aria-label кнопок ↑↓✕ бере ім'я з `form.watch("contributors")`. `language_codes` — `form.watch` + `toggleLanguage` через `getValues`/`setValue`. `legal_status` `<select>` → Radix `Select` (сентинел `__unset__`); умовні поля — `form.watch("legal_status")`. `message`/`submissionError` — `useState` (сетяться лише в submit-хендлері, не в ефекті → lint ok). **Прим.:** прибрано `resetForm({values})`→`form.reset(...)`; ефекту ре-ініціалізації по `initialDictionary` не додавав (Formik без `enableReinitialize` теж не мав). Тест: `fireEvent.change("Правовий статус")` → `userEvent` combobox+option.
- [x] Прибрати залежність `formik` з `package.json` ✅ — `bun remove formik`; жодного `import ... formik` не лишилось.
- [x] Оновити `useFocusFirstError` ✅ — API не змінювалось (приймає `submitCount`/`isSubmitting` числами/булями), лише оновлено doc-коментар (Formik → `formState.submitCount`). Виклики передають `form.formState.submitCount` / `form.formState.isSubmitting`.
- [~] `hooks/usePageRangeEditor.ts` + `components/PageRangeEditor.tsx` — **не чіпав**: хук на чистому `useState`, Formik не вживав. Перепис на `useFieldArray`+zod = ризик без виграшу (динамічна валідація від `pageCount`, merge-on-save). Лишаю як є.
- [~] `components/ProjectMemberForm.tsx` — **не чіпав**: на чистому `useState` (email+role), Formik не вживав. `<select>` уже Radix. Перепис на RHF — зайва церемонія.

_Форм-блок: type-check ✅, lint ✅ (2 warning: `button.tsx` + `form.tsx` `react-refresh/only-export-components` — як у наявному `button.tsx`, прийнятно), build ✅ (CSS 41.39 kB), 205/205 ✅. Спільні `.form-field`/`.field-error`/`.form-error` лишаються у `styles.css` — вживаються по всьому застосунку (40+ місць), не лише у формах; окремий пункт очистки._

### Крок 3 — Компоненти (по одному, з перевіркою та diff)

- [x] `components/ApiStatus.tsx` ✅ — `.status-indicator` → `flex items-center gap-[0.6rem] font-[650]`; `.status-dot` → `size-[0.7rem] rounded-full bg-muted-dot` + `cn(…, available && "bg-[#158052] shadow-[0_0_0_0.3rem_#dff3e9]", unavailable && "bg-[#b43c2d] shadow-[0_0_0_0.3rem_#f9e3df]")` (кольори точкові — не токени). Мертвий `.status-card` (+ його `@media 38rem`, вже замінений `<Card asChild>` + утилітами раніше) видалено. Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅.
- [x] `components/AuthActions.tsx` ✅ — вже на утилітах (`.header-actions` → `ml-auto flex items-center gap-4`, `.logout-error` → `m-0 max-w-[28rem] text-[0.9rem] text-destructive`, link-кнопки на `<Button asChild>`); зроблено разом із оболонкою.
- [x] `components/AuthProvider.tsx` ✅ — розмітки/класів немає (context provider).
- [x] `components/DictionaryMetadataForm.tsx` (частково) ✅ — `.contributor-fieldset` → `border-0 p-0`; `legend` → `p-0 font-bold`; `.contributor-list` → `my-3 grid list-none gap-[0.6rem] p-0`; `.contributor-row` → `grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-2`; `.contributor-row input/select` → `min-h-[2.6rem] rounded-[0.5rem] border border-input px-[0.65rem] py-2` (безкласові Formik-поля — інпути/select лишаю нативними, RHF-перепис у блоці форм); `.language-grid` → `grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-[0.6rem]`; `.missing-fields` → `rounded-[0.6rem] bg-warning px-4 py-3 text-[0.92rem] text-warning-foreground`. Мертві CSS-правила знято тут-таки: `.secondary-button`/`.danger-button`/`.icon-button`(+`:disabled`) (→ `<Button>`), `.progress-track`/`.progress-bar` (→ `<Progress>`), `.language-option`, `.checkbox-field`, `.contributor-*`. Лишається: `.dictionary-form`, `.form-section`(+`h2`), `.section-hint` — спільні, з блоком форм / сторінок. Перевірено: type-check ✅, lint ✅, build ✅ (CSS 41.12 kB), 205/205 ✅.
- [x] `components/DictionarySourceUpload.tsx` (частково) ✅ — `.file-summary` → `m-0 font-[650] text-primary-strong` (у 2 файлах: тут + `DictionaryMetadataForm`); CSS-правило видалено. `.form-field` (інпут файлу) + `.section-hint`/`.field-error`/`.form-actions` лишаються — спільні, підуть із блоком форм.
- [x] `components/DictionaryReadiness.tsx` ✅ — `.readiness-blockers` → `mt-2 mb-0 list-disc pl-5 text-[0.92rem]` (**додано `list-disc`**: старий CSS мав `padding-left:1.25rem` під маркери, але Tailwind preflight `ul{list-style:none}` їх прибирав — на audit-гілці повертаю список як список). Мертві `.status-badge`/`--draft`/`--configured` (вже замінені `<Badge>`) видалено. `.missing-fields` лишається — вживає `DictionaryMetadataForm` (окремий крок). Перевірено: type-check ✅, lint ✅, build ✅ (CSS 44.55 kB), 205/205 ✅.
- [x] `components/PageRangeEditor.tsx` ✅ — `.page-range-list` → `my-3 grid list-none gap-[0.6rem] p-0`; `.page-range-row` → `grid grid-cols-[6rem_auto_6rem_auto] items-center gap-2`; `.page-range-row input` → `<Input>` (shadcn) з `className="min-h-[2.6rem] px-[0.65rem] py-2"` для збереження щільнішого рядка; `.page-range-row .field-error` (grid-column 1/-1) → `col-span-full` поряд із класом `field-error` (сам `field-error` лишається — спільний). CSS-правила `.page-range-*` видалено з `@layer legacy`. Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅.
- [x] `components/ScanProgressBar.tsx` ✅ — `.scan-progress` → `grid w-full gap-[0.6rem]`, `.scan-progress-summary` → `m-0 font-[650] tabular-nums`, `.scan-progress-pages` → `flex max-h-24 flex-wrap gap-[0.3rem] overflow-y-auto overscroll-contain`, плитка `.scan-progress-page` → `min-w-8 rounded-[0.35rem] border bg-surface px-[0.4rem] py-1 text-center text-[0.8rem] text-foreground tabular-nums [content-visibility:auto] [contain-intrinsic-size:auto_1.8rem] aria-[current=page]:[outline:2px_solid_var(--color-selected)] aria-[current=page]:outline-offset-1` + `cn(…, has_lexemes && "border-primary bg-secondary font-[650] text-primary")` (= `--processed`). `.ocr-suggestions-controls` → `mb-3 flex items-center gap-3` (клас лишається — ще вживає `DictionaryPageViewer`). **Прим.:** базовій плитці додано `text-foreground` — раніше без власного `color` вона брала `#fff` від глобального `button{}` (білий на білому). Тест `--processed`-класу переписано на перевірку `title`. Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅.
- [x] `components/DictionaryPageViewer.tsx` ✅ — `.page-viewer` → `grid justify-items-center gap-4`; `.ocr-suggestions-controls` → `mb-3 flex items-center gap-3` (**останній вжиток — CSS-правило видалено**); `.page-viewer-body` (+ `@media 768px`) → `grid w-full grid-cols-[minmax(0,1fr)_minmax(16rem,20rem)] items-start gap-6 max-md:grid-cols-[1fr]`; `.lexeme-sidebar` → `grid content-start gap-[0.6rem]`, `.lexeme-sidebar h3` → `text-base`; `.page-viewer-nav` → `flex items-center gap-4`; `.page-viewer-counter` → `min-w-40 text-center font-[650] tabular-nums`. `.page-viewer-image` лишається — вживає `LexemeCanvas` (окремий крок). Порядок імпортів виправлено. Перевірено: type-check ✅, lint ✅, build ✅ (CSS 44.12 kB), 205/205 ✅.
- [x] `components/LexemeCanvas.tsx` ✅ (**піксель-в-піксель**) — `.lexeme-canvas-wrap` → `grid justify-items-center gap-3`; `.lexeme-canvas` → `relative inline-block cursor-crosshair select-none`; `.page-viewer-image` (+ `.lexeme-canvas .page-viewer-image{display:block}`) → `block max-h-[80vh] max-w-full rounded-[0.75rem] border bg-surface`; `.lexeme-box` (+`--clickable`) → `pointer-events-auto absolute cursor-pointer border-2 border-lexeme bg-[rgb(217_119_6_/_15%)]`; `--selected` → `border-[3px] border-selected bg-[rgb(185_28_28_/_18%)]` (через `cn`); `--draft` → `pointer-events-none absolute border-2 border-dashed border-primary bg-[rgb(36_88_71_/_12%)]`; `--pending` → те саме без dashed, `/_18%`; `--suggestion` (`<button>`) → `pointer-events-auto absolute cursor-pointer rounded-none border-2 border-dashed border-lexeme-suggestion bg-[rgb(37_99_235_/_10%)] p-0 hover:bg-[rgb(37_99_235_/_22%)]`. `.lexeme-resize-handle` → `pointer-events-auto absolute size-[10px] rounded-[2px] border border-white bg-selected` + `HANDLE_CLASSES: Record<HandleId,string>` (per-handle `left/right/top/bottom-[-5px]`, `left-1/2 -translate-x-1/2` тощо + `cursor-*-resize`); додано `data-handle={handle}` (стабільний хук замість `.lexeme-resize-handle--se` у тесті). `.lexeme-form` → `grid w-[min(100%,24rem)] gap-2`; `.lexeme-form input` → `<Input>` + `min-h-[2.6rem] rounded-[0.5rem] px-[0.65rem] py-2`. Тести: 3 у `LexemeCanvas.test` + 1 у `DictionaryPageViewer.test` переведено з `lexeme-box--selected`/`--suggestion`/`.lexeme-resize-handle--se` на `border-selected`/`border-lexeme-suggestion`/`[data-handle="se"]`. Перевірено: type-check ✅, lint ✅, build ✅ (CSS 43.60 kB), 205/205 ✅.
- [x] `components/LexemeList.tsx` ✅ — `.lexeme-list` → `m-0 grid max-h-[70vh] list-none gap-2 overflow-y-auto overscroll-contain p-0`; `.lexeme-list-row` → `grid gap-[0.35rem]`; `.lexeme-list-item` → `grid w-full gap-[0.2rem] rounded-[0.5rem] border bg-surface px-3 py-[0.6rem] text-left text-foreground` + `cn(…, selected && "border-selected bg-[rgb(185_28_28_/_8%)]")`; `.lexeme-list-item-text` → `font-[650] [overflow-wrap:anywhere]`; `.lexeme-list-item-meta` → `text-[0.85rem] text-muted-foreground tabular-nums`; `.lexeme-list-item input` → `<Input>` + `className="min-h-[2.2rem] rounded-[0.4rem] px-2 py-[0.35rem] font-[650]"`; `.lexeme-list-actions` → `flex flex-wrap gap-[0.4rem] [&_button]:px-[0.6rem] [&_button]:py-[0.35rem] [&_button]:text-[0.85rem]` (descendant-варіант зберігає стару перевагу над `size="sm"`). **Прим.:** `text-foreground` на item-`<button>` — той самий білий-на-білому баг (`.lexeme-list-item` не мав `color` → `button{color:#fff}`), виправлено на audit-гілці. `.lexeme-sidebar`/`.lexeme-form` — не тут (Viewer/Canvas). Перевірено: type-check ✅, lint ✅, build ✅ (CSS 43.84 kB), 205/205 ✅.
- [x] `components/EntryFragmentCrop.tsx` ✅ — `.entry-fragment-preview` (в `EntryDetailPage`) → `grid gap-2 mb-4`; `.entry-fragment-crop` → `relative max-w-full overflow-hidden rounded-[0.75rem] border bg-surface`; `.entry-fragment-crop-image` → `absolute max-w-none`; `.entry-fragment-crop-box` → `pointer-events-none absolute border-2 border-lexeme bg-[rgb(217_119_6_/_12%)]`. CSS-правила видалено. Перевірено: type-check ✅, lint ✅, build ✅ (CSS 43.36 kB), 205/205 ✅.
- [x] `components/AbbreviationForm.tsx` (частково) ✅ — `.contributor-fieldset`/`legend`/`.contributor-list`/`.contributor-row`(+input) → ті самі утиліти, що в `DictionaryMetadataForm` (варіанти написання). Лишається: `.form-field`, `<select>` (Formik), `.form-actions`, `.form-error` — спільні, з блоком форм.
- [x] `components/AbbreviationsTable.tsx` ✅ — `.table-actions` → `flex flex-wrap gap-2`. Мертвий CSS видалено: `.table-actions`, `.badge` + всі `.badge--*` (давно замінені на shadcn `<Badge variant>`), `.table-wrapper` + `.abbreviation-table`/`.settlement-table`/`.member-table` (+ th/td) — давно замінені на shadcn `<Table>`. Перевірено: type-check ✅, lint ✅, build ✅ (CSS 42.02 kB), 205/205 ✅.
- [x] `components/AbbreviationImportPanel.tsx` ✅ — своїх класів немає; кнопки/статуси вже на `<Button>`/`<Badge>`/`<Table>`. Лишок — лише спільні `.form-section`/`.section-hint`/`.form-actions` → блок форм/сторінок.
- [x] `components/SettlementForm.tsx` ✅ — своїх класів немає (вкладений `SettlementSearchCombobox` мігровано окремо). Лишок — спільні `.form-section`/`.form-field`/`.form-actions` → блок форм.
- [x] `components/SettlementSearchCombobox.tsx` ✅ — `.settlement-search` → `flex flex-col gap-3`; `.settlement-search-results` → `m-0 flex list-none flex-col gap-[0.4rem] p-0`; CSS-правила видалено. 3×`<select>` вже на shadcn `Select` (сентинел `__all__`), інпут — на `Input`. Порядок імпортів виправлено. Перевірено: type-check ✅, lint ✅, build ✅ (CSS 44.24 kB), 205/205 ✅.
- [x] `components/SettlementsTable.tsx` ✅ — `.table-actions` → `flex flex-wrap gap-2` (решта — спільний мертвий CSS, знято разом з `AbbreviationsTable`).
- [x] `components/SettlementImportPanel.tsx` ✅ — як `AbbreviationImportPanel`: своїх класів немає, лишок спільний → блок форм.
- [x] `components/ProjectMemberForm.tsx` ✅ — своїх класів немає; `<select>` вже на shadcn `Select`. Лишок — спільні `.form-section`/`.form-field`/`.form-actions`/`.form-error` → блок форм.
- [x] `components/ProjectMembersTable.tsx` ✅ — `.member-table` знято (мертвий, → `<Table>`); рядковий `<select>` вже на shadcn `Select`. Лишок — `.field-error` (спільний) → блок форм.

### Крок 3 — Сторінки (по одному, з перевіркою та diff)

**Спільні `@utility` (JSX без змін, класи ті самі):** `.dictionary-form` → `@utility` (`mt-8 grid gap-6`); `.section-hint` → `@utility` (`mt-[-0.6rem] text-[0.92rem] text-muted-foreground`); `.form-actions` → `@utility` (`flex flex-wrap gap-3`); `.form-field` → `@utility` (`grid gap-[0.45rem]`); `.field-hint`/`.field-error`/`.form-error` → `@utility` (`mb-0 text-[0.88rem]` + `text-muted-foreground`/`text-destructive`). Лишаються тільки descendant-правила `.form-field input/select/textarea` (фолбек для безкласових полів; shadcn `<Input>`/`<Textarea>` їх перекривають) + `.form-section h2` + `.auth-card h1`.

- [x] `pages/LoginPage.tsx` ✅ — `.auth-page`/`.auth-card` → `@utility` (JSX без змін); `.auth-intro` → `leading-relaxed text-muted-foreground`; `.oauth-divider` → `my-6 text-center text-[0.88rem] text-muted-foreground`; `.google-oauth-button` (+hover/focus) → `flex justify-center rounded-[0.55rem] border border-input px-[0.8rem] py-[0.65rem] font-[650] text-foreground no-underline hover:border-primary hover:bg-[#f4f7f4] focus-visible:… focus-visible:[outline:3px_solid_var(--color-ring-subtle)]`.
- [x] `pages/RegisterPage.tsx` ✅ — `.auth-card auth-card--result` → `auth-card text-center`; `.auth-intro`/`.result-message` → `leading-relaxed text-muted-foreground`; h1 → `mx-auto` (для `--result`). `.language-grid` — насправді в `DictionaryMetadataForm`, не тут (вже мігровано).
- [x] `pages/ForgotPasswordPage.tsx` ✅ — те саме (2× `.auth-intro`, `--result`).
- [x] `pages/ResetPasswordPage.tsx` ✅ — `.result-message--error` → `text-destructive`; решта як вище.
- [x] `pages/VerifyEmailPage.tsx` ✅ — динамічний `result-message--${kind}` → `RESULT_TONE` мапа (`loading`→`text-muted-foreground`, `success`→`text-success-foreground`, `error`→`text-destructive`) + `leading-relaxed`; `auth-card--result` → `auth-card text-center` + `h1 mx-auto`.
- [x] `.result-message--success` (8 місць поза auth: ArticleSchemaPage, EntryDetailPage ×2, Settlement/AbbreviationImportPanel, PageRangeEditor, DictionaryMetadataForm) → `m-0 text-[0.88rem] text-success-foreground`. Колір `#17663f` зведено до `--color-success-foreground` #175c3a (рішення №3). Легасі-правила `.auth-*`/`.result-message*`/`.oauth-*`/`.google-oauth-*`/`.primary-link`/`.secondary-link` (мертві) видалено.
- [x] `pages/DashboardPage.tsx` ✅ — своїх класів немає; лише `.page`/`.hero`/`.lede`/`.eyebrow` (`@utility`) + inline-утиліти.
- [x] `pages/DictionaryFormPage.tsx` / `DictionaryViewerPage.tsx` / `PageRangesPage.tsx` / `ProjectMembersPage.tsx` / `AbbreviationsPage.tsx` / `SettlementsPage.tsx` ✅ — своїх класів не лишилось: усе на `@utility` (`.page`/`.dictionary-form`/`.form-section`/`.section-hint`/`.form-actions`/`.form-error`) + мігровані компоненти (`<Card>`/`<Table>`/`<Button>`/RHF-форми).
- [x] `pages/ArticleSchemaPage.tsx` ✅ — `.schema-field-tree` (безкласове дерево, preflight з'їв маркери/відступ — той самий регрес, що `.readiness-blockers`) → `my-2 grid list-disc gap-1 pl-5`; `.schema-field-name` → `font-[650]` (мало бути виділене, ніколи не стилізувалось). `.form-error` — `@utility`.
- [x] `pages/EntryDetailPage.tsx` ✅ — `.entry-field-list` (теж безкласове, дефолтні bullet-и на рядках із кнопками) → `grid list-none gap-4 p-0` (як `.lexeme-list`); `.entry-field-row` → `grid gap-2`. `.entry-fragment-preview` вже мігровано (EntryFragmentCrop). Безкласові `<select>`/`<input>` у `FieldRow`/`AddFieldForm` — фолбек-правило `.form-field input/select` на них **не** діє (вони не в `.form-field`); лишаються з browser-default виглядом як і на `main` — окремий пункт (не регрес міграції).
- [x] `pages/DictionariesList.tsx` ✅ — `.dictionary-grid` → `m-0 mt-8 grid list-none grid-cols-[repeat(auto-fill,minmax(16rem,1fr))] gap-5 p-0`; `.dictionary-thumbnail` → `block h-56 w-full bg-secondary object-cover object-top`; `--placeholder` → `flex h-56 w-full items-center justify-center bg-secondary p-4 text-center text-[0.88rem] text-muted-foreground`; `.dictionary-card-body` → `grid gap-2 p-5`; `h2` → `mb-0 text-[1.2rem]`; `.dictionary-card-actions` → `mt-2 flex flex-wrap items-center gap-3`. `.dictionary-card` (мертвий, → `<Card>`) + `.secondary-link` descendant видалено. CSS 40.4 kB. Перевірено: type-check ✅, lint ✅, build ✅, 205/205 ✅.
- [ ] `pages/DictionaryFormPage.tsx` — обгортка `.page`, `.form-actions`
- [ ] `pages/DictionaryViewerPage.tsx` — `.page` + viewer
- [ ] `pages/PageRangesPage.tsx` — `.page` + editor
- [ ] `pages/ProjectMembersPage.tsx` — `.page` + table/form
- [ ] `pages/AbbreviationsPage.tsx` — `.page` + table/form/import
- [ ] `pages/SettlementsPage.tsx` — `.page` + table/form/import
### Крок 4 — Прибирання

**Стан:** усі кастомні класи мігровано. `grep` по `src/` не знаходить жодного класу поза `@utility`-набором (`auth-page`/`auth-card`/`dictionary-form`/`form-field`/`form-section`/`section-hint`/`form-actions`/`field-error`/`form-error`/`status-label`/`page`/`hero`/`lede`/`eyebrow`). У `@layer legacy` лишилось **тільки**: глоб. reset (`:root` шрифт/колір/тло, `* box-sizing`, `html scroll-behavior` + `prefers-reduced-motion`, `body`, `a`, `button` + стани, `a:focus-visible`), глоб. типографіка (`h1,h2,p` margin-top; `h1,h2,h3` text-wrap; `h1` розмір/шрифт), і 3 descendant-твіки (`.auth-card h1`, `.form-section h2`, `.form-field label` + `.form-field input/select/textarea` як фолбек для безкласових полів).

- [ ] Глобальний `button {}` reset (`border-radius:999px; padding:.7rem 1rem; color:#fff; background:#245847; …`) — джерело «білого-на-білому». shadcn `<Button>` уже все перекриває; лишається як фолбек для кількох безкласових `<button>`. Рішення: або звузити до безпечного мінімуму (`cursor:pointer; font:inherit`), або дати решті `<button>` явні класи. **Потрібне рішення користувача.**
- [ ] Глобальний `h1` (`font-family: Georgia; font-size: clamp(2.75rem,8vw,5.75rem); font-weight:500; …`) — вирішити: лишити як базову типографіку чи винести в `@utility`/компонент.
- [ ] Безкласові `<select>`/`<input>` у `EntryDetailPage` `FieldRow`/`AddFieldForm` → `<Input>` + Radix `Select` (не регрес, але єдине місце з browser-default полями).
- [x] `bun run test` / `build` / `type-check` / `lint` — зелено (205/205; 2 warning `react-refresh` у `button.tsx`+`form.tsx`).
- [ ] Ручна візуальна перевірка кожної сторінки.

### Інструменти перевірки (Крок 3, per-component)

- Playwright **не ставимо**. Перевірка кожного компонента: ручний скріншот before/after + прогін наявних Vitest-тестів (`bun run test`) + `bun run type-check`.

---

## 4. Рішення (узгоджено 2026-08-28)

| # | Питання | Рішення |
|---|---------|---------|
| 1 | Розташування файлу плану | Лишається `apps/web/MIGRATION_PLAN.md` |
| 2 | Muted-текст (`#50605a`/`#61726b`/`#527064`) | Звести до одного `--color-muted-foreground: #61726b` |
| 3 | Success/warning/info/danger пари | Звести кожну до однієї пари fg/bg (значення в §2) |
| 4 | Focus ring | `--color-ring: #d58d36` (кнопки/посилання); окремий `--color-ring-subtle: #dcebe5` для інпутів |
| 5 | Нативні `<select>` | Мігрувати на shadcn/Radix `Select` |
| 6 | Dark mode | Не додаємо |
| 7 | Playwright | Не ставимо — ручні скріншоти + Vitest |
| 8 | Порядок | Примітиви → форми → layout → компоненти → сторінки → прибирання |
| — | Formik | Повна міграція на `react-hook-form` + shadcn `Form` + `zod` |

---

## 5. Ризики

- Глобальні селектори по тегах (`button`, `a`, `h1/h2/h3`, `input` у `.form-field`) впливають на весь застосунок. Їхні правила прибираємо **лише після** міграції всіх споживачів — інакше проміжні коміти матимуть «голі» елементи.
- **Formik → react-hook-form** — найбільший блок роботи (9 форм + field-arrays + ~8 тест-файлів). Валідацію переносимо в `zod`-схеми 1:1; поведінку (коли показувати помилки, focus-first-error) звіряємо вручну.
- `Select`/`Checkbox` від Radix у контрольованих формах підключаємо через `Controller`.
- `LexemeCanvas` та `entry-fragment-crop` — точні піксельні позиції (`position: absolute`, resize-курсори). Мігрувати обережно, з візуальним порівнянням.
- Тести (`*.test.tsx`) місцями шукають елементи за класами/структурою — оновлювати разом з компонентом.
