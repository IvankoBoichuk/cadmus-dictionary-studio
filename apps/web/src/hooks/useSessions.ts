import { useCallback, useEffect, useState } from "react";

import { API, apiMessageFrom, isAbortError, type SessionSummary } from "../api";

export type SessionsLoadState =
  | { status: "loading" }
  | { status: "loaded"; sessions: SessionSummary[] }
  | { status: "error"; message: string };

export type SessionsActionState = { pending: boolean; error: string | undefined };

/** Loads the signed-in user's active sessions and offers revoke actions. */
export function useSessions() {
  const [state, setState] = useState<SessionsLoadState>({ status: "loading" });
  const [action, setAction] = useState<SessionsActionState>({
    pending: false,
    error: undefined,
  });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    API.auth.listSessions({ signal: controller.signal }).then(
      (response) => {
        if (active) setState({ status: "loaded", sessions: response.sessions });
      },
      (error: unknown) => {
        if (!active || isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ??
            "Не вдалося завантажити активні сесії. Спробуйте пізніше.",
        });
      },
    );
    return () => {
      active = false;
      controller.abort();
    };
  }, [reloadKey]);

  const reload = useCallback(() => {
    setState({ status: "loading" });
    setReloadKey((key) => key + 1);
  }, []);

  const revoke = useCallback(async (sessionId: string): Promise<void> => {
    setAction({ pending: true, error: undefined });
    try {
      await API.auth.revokeSession(sessionId);
      setState((current) =>
        current.status === "loaded"
          ? {
              ...current,
              sessions: current.sessions.filter((s) => s.id !== sessionId),
            }
          : current,
      );
      setAction({ pending: false, error: undefined });
    } catch (error) {
      setAction({
        pending: false,
        error:
          apiMessageFrom(error) ??
          "Не вдалося завершити сесію. Спробуйте пізніше.",
      });
    }
  }, []);

  const revokeOthers = useCallback(async (): Promise<void> => {
    setAction({ pending: true, error: undefined });
    try {
      await API.auth.revokeOtherSessions();
      setState((current) =>
        current.status === "loaded"
          ? { ...current, sessions: current.sessions.filter((s) => s.current) }
          : current,
      );
      setAction({ pending: false, error: undefined });
    } catch (error) {
      setAction({
        pending: false,
        error:
          apiMessageFrom(error) ??
          "Не вдалося завершити інші сесії. Спробуйте пізніше.",
      });
    }
  }, []);

  return { state, action, revoke, revokeOthers, reload } as const;
}
