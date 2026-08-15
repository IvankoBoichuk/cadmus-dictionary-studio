import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { API, isAbortError } from "../api";
import { useAuth } from "../authContext";

export type LogoutState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "error"; message: string };

export function useLogout(): { state: LogoutState; logout(): void } {
  const { setAnonymous } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState<LogoutState>({ status: "idle" });
  const request = useRef<AbortController | null>(null);

  useEffect(() => () => request.current?.abort(), []);

  const logout = useCallback(() => {
    if (request.current) return;

    const controller = new AbortController();
    request.current = controller;
    setState({ status: "submitting" });
    void API.auth.logout({ signal: controller.signal }).then(
      () => {
        request.current = null;
        setAnonymous();
        navigate("/login", { replace: true });
      },
      (error: unknown) => {
        request.current = null;
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            "Не вдалося підтвердити вихід із системи. Перевірте з’єднання та спробуйте ще раз.",
        });
      },
    );
  }, [navigate, setAnonymous]);

  return { state, logout };
}
