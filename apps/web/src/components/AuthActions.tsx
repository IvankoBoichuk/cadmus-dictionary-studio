import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

import { useAuth } from "../authContext";
import { useLogout } from "../hooks/useLogout";

export function AuthActions() {
  const { session } = useAuth();
  const { state, logout } = useLogout();

  if (session.status !== "authenticated") {
    return (
      <nav
        className="ml-auto flex items-center gap-4"
        aria-label="Автентифікація"
      >
        <Button asChild className="px-[1.1rem] py-3">
          <Link to="/register">Зареєструватися</Link>
        </Button>
        <Link
          className="inline-block font-[650] text-primary hover:underline"
          to="/login"
        >
          Увійти
        </Link>
      </nav>
    );
  }

  return (
    <div className="ml-auto flex items-center gap-4">
      <Button
        type="button"
        disabled={state.status === "submitting"}
        onClick={logout}
      >
        {state.status === "submitting" ? "Виходимо…" : "Вийти"}
      </Button>
      {state.status === "error" && (
        <p
          className="m-0 max-w-[28rem] text-[0.9rem] text-destructive"
          role="alert"
        >
          {state.message}
        </p>
      )}
    </div>
  );
}
