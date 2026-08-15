import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { API, ApiError, isAbortError, type AuthenticatedUser } from "../api";
import {
  AuthContext,
  type AuthContextValue,
  type SessionState,
} from "../authContext";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    void API.auth.currentSession().then(
      (user) => {
        if (active) setState({ status: "authenticated", user });
      },
      (error: unknown) => {
        if (!active || isAbortError(error)) return;
        if (error instanceof ApiError && error.status === 401) {
          setState({ status: "anonymous" });
          return;
        }
        setState({ status: "unavailable" });
      },
    );
    return () => {
      active = false;
    };
  }, []);

  const setAuthenticated = useCallback((user: AuthenticatedUser) => {
    setState({ status: "authenticated", user });
  }, []);
  const value: AuthContextValue = useMemo(
    () => ({ session: state, setAuthenticated }),
    [setAuthenticated, state],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
