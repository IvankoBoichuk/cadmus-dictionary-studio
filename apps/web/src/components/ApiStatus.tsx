import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

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
    <Card
      asChild
      className="mt-[clamp(3rem,8vw,6rem)] grid grid-cols-[minmax(8rem,1fr)_auto_auto] items-center gap-6 p-6 max-[38rem]:grid-cols-[1fr]"
    >
      <section aria-labelledby="api-status-title">
        <div>
          <p className="status-label">Стан системи</p>
          <h2 id="api-status-title" className="mb-0 text-xl">
            API
          </h2>
        </div>
        <div
          className="flex items-center gap-[0.6rem] font-[650]"
          role="status"
        >
          <span
            aria-hidden="true"
            className={cn(
              "size-[0.7rem] rounded-full bg-muted-dot",
              state === "available" &&
                "bg-[#158052] shadow-[0_0_0_0.3rem_#dff3e9]",
              state === "unavailable" &&
                "bg-[#b43c2d] shadow-[0_0_0_0.3rem_#f9e3df]",
            )}
          />
          {state === "checking" && "Перевіряємо доступність…"}
          {state === "available" && "Доступний"}
          {state === "unavailable" && "Недоступний"}
        </div>
        {state === "unavailable" && (
          <Button
            type="button"
            className="max-[38rem]:justify-self-start"
            onClick={() => {
              void retry();
            }}
          >
            Спробувати знову
          </Button>
        )}
      </section>
    </Card>
  );
}
