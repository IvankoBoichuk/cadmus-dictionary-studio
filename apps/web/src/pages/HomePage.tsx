import {
  FileDown,
  Gauge,
  Layers,
  ScanLine,
  ShieldCheck,
  SquarePen,
  Upload,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

import heroImage from "../assets/cadmus-hero.png";

type Offer = {
  icon: typeof Upload;
  title: string;
  description: string;
};

const offer: Offer[] = [
  {
    icon: Upload,
    title: "Завантаження джерел",
    description:
      "Скани та PDF друкованих словників потрапляють у робочий простір разом із діапазонами сторінок і метаданими видання.",
  },
  {
    icon: ScanLine,
    title: "Розпізнавання структури",
    description:
      "OCR і сегментація ALTO виділяють межі статей, реєстрові слова та поля за схемою словникової статті.",
  },
  {
    icon: SquarePen,
    title: "Перевірка та виправлення",
    description:
      "Редактори звіряють кожну статтю зі сканом, коригують поля й позначають готовність до публікації.",
  },
  {
    icon: FileDown,
    title: "Структурований експорт",
    description:
      "Перевірені дані стають придатними для повторного використання наборами з посиланням на джерело кожного запису.",
  },
];

type Benefit = {
  icon: typeof Upload;
  title: string;
  description: string;
};

const benefits: Benefit[] = [
  {
    icon: Gauge,
    title: "Швидше від ручного набору",
    description:
      "Автоматична сегментація прибирає механічну працю — команда працює над змістом, а не над перенабором тексту.",
  },
  {
    icon: ShieldCheck,
    title: "Збережене походження",
    description:
      "Кожен запис зберігає посилання на сторінку й фрагмент скану, тож рішення редактора завжди можна перевірити.",
  },
  {
    icon: Users,
    title: "Спільна робота команди",
    description:
      "Ролі учасників, статуси статей і діапазони сторінок тримають великий словниковий проєкт узгодженим.",
  },
  {
    icon: Layers,
    title: "Контроль якості",
    description:
      "Стани готовності та перелік блокерів показують, що заважає опублікувати словник саме зараз.",
  },
];

export function HomePage() {
  return (
    <main className="page" id="main-content">
      <section
        aria-labelledby="page-title"
        className="grid items-center gap-[clamp(2rem,6vw,4rem)] lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]"
      >
        <div className="hero">
          <p className="eyebrow">Лексикографічний робочий простір</p>
          <h1 id="page-title">Cadmus Dictionary Studio</h1>
          <p className="lede">
            Cadmus перетворює скани та PDF друкованих словників на перевірені
            структуровані лексикографічні дані — зі збереженням посилання на
            джерело кожного запису.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild className="px-[1.1rem] py-3">
              <Link to="/register">Створити акаунт</Link>
            </Button>
            <Button asChild variant="secondary" className="px-[1.1rem] py-3">
              <Link to="/login">Увійти</Link>
            </Button>
          </div>
        </div>
        <img
          src={heroImage}
          alt="Кадм вручає фінікійську абетку — гравюра за мотивами античного міфу"
          width={845}
          height={1045}
          fetchPriority="high"
          className="mx-auto w-full max-w-[22rem] object-contain aspect-4/5 lg:max-w-none"
        />
      </section>

      <section
        aria-labelledby="offer-title"
        className="mt-[clamp(3rem,9vw,6rem)]"
      >
        <p className="eyebrow">Пропозиція</p>
        <h2 id="offer-title" className="text-[clamp(1.6rem,4vw,2.4rem)]">
          Шлях від скану до даних
        </h2>
        <p className="lede">
          Чотири кроки одного конвеєра — від завантаження видання до
          структурованого набору, готового до повторного використання.
        </p>
        <ol className="mt-8 grid list-none gap-4 p-0 [grid-template-columns:repeat(auto-fit,minmax(15rem,1fr))]">
          {offer.map((item, index) => (
            <Card asChild key={item.title} className="p-6">
              <li>
                <span
                  aria-hidden="true"
                  className="flex size-11 items-center justify-center rounded-full bg-secondary text-secondary-foreground"
                >
                  <item.icon className="size-5" />
                </span>
                <p className="mt-4 mb-1 text-[0.75rem] font-[750] tracking-[0.12em] text-muted-foreground uppercase">
                  Крок {index + 1}
                </p>
                <h3 className="mb-2 text-[1.1rem]">{item.title}</h3>
                <p className="mb-0 text-[0.95rem] leading-[1.6] text-muted-foreground">
                  {item.description}
                </p>
              </li>
            </Card>
          ))}
        </ol>
      </section>

      <section
        aria-labelledby="benefits-title"
        className="mt-[clamp(3rem,9vw,6rem)]"
      >
        <p className="eyebrow">Переваги</p>
        <h2 id="benefits-title" className="text-[clamp(1.6rem,4vw,2.4rem)]">
          Чому команди обирають Cadmus
        </h2>
        <ul className="mt-8 grid list-none gap-4 p-0 [grid-template-columns:repeat(auto-fit,minmax(15rem,1fr))]">
          {benefits.map((item) => (
            <li
              key={item.title}
              className="flex gap-4 rounded-lg border bg-card p-6"
            >
              <span
                aria-hidden="true"
                className="flex size-11 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground"
              >
                <item.icon className="size-5" />
              </span>
              <div>
                <h3 className="mb-2 text-[1.1rem]">{item.title}</h3>
                <p className="mb-0 text-[0.95rem] leading-[1.6] text-muted-foreground">
                  {item.description}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
