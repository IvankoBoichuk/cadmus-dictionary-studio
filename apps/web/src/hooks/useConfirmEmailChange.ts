import { useEffect, useState } from "react";

import { API, apiMessageFrom } from "../api";

export type ConfirmEmailChangeState =
  | { kind: "loading"; message: string }
  | { kind: "success"; message: string }
  | { kind: "error"; message: string };

const LOADING_STATE: ConfirmEmailChangeState = {
  kind: "loading",
  message: "Підтверджуємо нову адресу…",
};
const MISSING_TOKEN_STATE: ConfirmEmailChangeState = {
  kind: "error",
  message: "У посиланні немає токена підтвердження.",
};

function failureState(error: unknown): ConfirmEmailChangeState {
  return {
    kind: "error",
    message:
      apiMessageFrom(error) ??
      "Сервіс підтвердження недоступний. Спробуйте пізніше.",
  };
}

export function useConfirmEmailChange(
  token: string | null,
): ConfirmEmailChangeState {
  const [resolution, setResolution] = useState<{
    token: string;
    state: ConfirmEmailChangeState;
  } | null>(null);

  useEffect(() => {
    if (!token) return;

    let ignore = false;
    void API.auth.confirmEmailChange({ token }).then(
      ({ message }) => {
        if (!ignore) {
          setResolution({
            token,
            state: {
              kind: "success",
              message:
                message ?? "Email оновлено. Тепер увійдіть з новою адресою.",
            },
          });
        }
      },
      (error: unknown) => {
        if (!ignore) setResolution({ token, state: failureState(error) });
      },
    );

    return () => {
      ignore = true;
    };
  }, [token]);

  if (!token) return MISSING_TOKEN_STATE;
  return resolution?.token === token ? resolution.state : LOADING_STATE;
}
