import { Link } from "react-router-dom";

import { useAuth } from "../authContext";
import { useLogout } from "../hooks/useLogout";

export function AuthActions() {
  const { session } = useAuth();
  const { state, logout } = useLogout();

  if (session.status !== "authenticated") {
    return (
      <nav className="header-actions" aria-label="Автентифікація">
        <Link className="primary-link" to="/register">
          Зареєструватися
        </Link>
        <Link className="secondary-link" to="/login">
          Увійти
        </Link>
      </nav>
    );
  }

  return (
    <div className="header-actions">
      <button
        type="button"
        disabled={state.status === "submitting"}
        onClick={logout}
      >
        {state.status === "submitting" ? "Виходимо…" : "Вийти"}
      </button>
      {state.status === "error" && (
        <p className="logout-error" role="alert">
          {state.message}
        </p>
      )}
    </div>
  );
}
