import { ApiStatus } from "../components/ApiStatus";

export function StatusPage() {
  return (
    <main className="page" id="main-content">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Стан системи</p>
        <h1 id="page-title">Стан системи</h1>
        <p className="lede">
          Поточна доступність сервісів Cadmus. Перевірка виконується у вашому
          браузері під час відкриття цієї сторінки.
        </p>
      </section>
      <ApiStatus />
    </main>
  );
}
