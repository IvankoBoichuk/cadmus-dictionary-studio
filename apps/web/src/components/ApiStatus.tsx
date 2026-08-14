import { useEffect, useState } from "react";

import { API_BASE_URL } from "../config";

type ApiState = "checking" | "available" | "unavailable";

const requestTimeoutMilliseconds = 5_000;

async function isApiAvailable(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(requestTimeoutMilliseconds),
    });

    if (!response.ok) {
      return false;
    }

    const result: unknown = await response.json();
    return (
      typeof result === "object" &&
      result !== null &&
      "status" in result &&
      result.status === "ok"
    );
  } catch {
    return false;
  }
}

export function ApiStatus() {
  const [state, setState] = useState<ApiState>("checking");

  useEffect(() => {
    let isCurrent = true;

    void isApiAvailable().then((isAvailable) => {
      if (isCurrent) {
        setState(isAvailable ? "available" : "unavailable");
      }
    });

    return () => {
      isCurrent = false;
    };
  }, []);

  const retry = async () => {
    setState("checking");
    setState((await isApiAvailable()) ? "available" : "unavailable");
  };

  return (
    <section className="status-card" aria-labelledby="api-status-title">
      <div>
        <p className="status-label">System status</p>
        <h2 id="api-status-title">API</h2>
      </div>
      <div className={`status-indicator status-indicator--${state}`} role="status">
        <span className="status-dot" aria-hidden="true" />
        {state === "checking" && "Перевіряємо доступність…"}
        {state === "available" && "Доступний"}
        {state === "unavailable" && "Недоступний"}
      </div>
      {state === "unavailable" && (
        <button
          type="button"
          onClick={() => {
            void retry();
          }}
        >
          Спробувати знову
        </button>
      )}
    </section>
  );
}
