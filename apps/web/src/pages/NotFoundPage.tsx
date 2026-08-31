import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <main className="page" id="main-content">
      <h1>Сторінку не знайдено</h1>
      <p>
        <Link to="/">Повернутися на головну</Link>
      </p>
    </main>
  );
}
