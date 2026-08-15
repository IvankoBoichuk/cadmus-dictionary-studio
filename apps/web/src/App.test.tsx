import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { App } from "./App";

afterEach(() => {
  window.history.replaceState({}, "", "/");
  vi.unstubAllGlobals();
});

it("renders the base application layout", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    ),
  );

  render(<App />);

  expect(
    screen.getByRole("heading", { name: "Cadmus Dictionary Studio" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Cadmus — головна" })).toHaveAttribute(
    "href",
    "/",
  );
});

it("renders a not-found route", () => {
  window.history.replaceState({}, "", "/missing");

  render(<App />);

  expect(
    screen.getByRole("heading", { name: "Сторінку не знайдено" }),
  ).toBeInTheDocument();
});

it("opens registration and shows validation errors beside fields", async () => {
  window.history.replaceState({}, "", "/register");
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "invalid" },
  });
  fireEvent.change(screen.getByLabelText("Пароль"), {
    target: { value: "short" },
  });
  fireEvent.change(screen.getByLabelText("Підтвердження пароля"), {
    target: { value: "different" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Створити акаунт" }));

  expect(
    await screen.findByText("Введіть коректну email-адресу."),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Email")).toHaveAttribute(
    "aria-describedby",
    "email-error",
  );
  expect(
    screen.getByText("Пароль має містити щонайменше 12 символів."),
  ).toBeInTheDocument();
  expect(screen.getByText("Паролі не збігаються.")).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(([url]) => url === "/api/auth/register"),
  ).toBe(false);
});

it("registers a user and asks them to verify email", async () => {
  window.history.replaceState({}, "", "/register");
  const fetchMock = vi.fn((input: RequestInfo | URL) =>
    String(input) === "/api/auth/session"
      ? Promise.resolve(sessionResponse(false))
      : Promise.resolve(
          new Response(
            JSON.stringify({
              status: "pending_verification",
              message: "Акаунт створено. Перевірте email, щоб активувати його.",
            }),
            { status: 201 },
          ),
        ),
  );
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);

  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "user@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Пароль"), {
    target: { value: "long-enough-password" },
  });
  fireEvent.change(screen.getByLabelText("Підтвердження пароля"), {
    target: { value: "long-enough-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Створити акаунт" }));

  expect(
    await screen.findByRole("heading", { name: "Перевірте email" }),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("/api/auth/register", {
    credentials: "same-origin",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: "user@example.com",
      password: "long-enough-password",
      password_confirmation: "long-enough-password",
    }),
  });
});

it("places duplicate email feedback beside the email field", async () => {
  window.history.replaceState({}, "", "/register");
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      String(input) === "/api/auth/session"
        ? Promise.resolve(sessionResponse(false))
        : Promise.resolve(
            new Response(
              JSON.stringify({
                errors: { email: "Ця email-адреса вже зареєстрована." },
              }),
              { status: 409 },
            ),
          ),
    ),
  );
  render(<App />);

  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "user@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Пароль"), {
    target: { value: "long-enough-password" },
  });
  fireEvent.change(screen.getByLabelText("Підтвердження пароля"), {
    target: { value: "long-enough-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Створити акаунт" }));

  expect(
    await screen.findByText("Ця email-адреса вже зареєстрована."),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Email")).toHaveAttribute(
    "aria-describedby",
    "email-error",
  );
});

it("activates an account from the verification link", async () => {
  window.history.replaceState({}, "", "/verify-email#token=one-time-token");
  const fetchMock = vi.fn((input: RequestInfo | URL) =>
    Promise.resolve(
      String(input) === "/api/auth/session"
        ? sessionResponse(false)
        : new Response(
            JSON.stringify({ message: "Email підтверджено. Акаунт активовано." }),
            { status: 200 },
          ),
    ),
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(
    await screen.findByRole("heading", { name: "Акаунт активовано" }),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("/api/auth/verify-email", {
    credentials: "same-origin",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: "one-time-token" }),
  });
});

it("shows the activation error returned for an unusable token", async () => {
  window.history.replaceState({}, "", "/verify-email#token=used-token");
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        String(input) === "/api/auth/session"
          ? sessionResponse(false)
          : new Response(
              JSON.stringify({
                code: "used",
                message: "Це посилання вже було використано.",
              }),
              { status: 400 },
            ),
      ),
    ),
  );

  render(<App />);

  await waitFor(() => {
    expect(
      screen.getByRole("heading", { name: "Не вдалося активувати акаунт" }),
    ).toBeInTheDocument();
  });
  expect(
    screen.getByText("Це посилання вже було використано."),
  ).toBeInTheDocument();
});

it("deduplicates one-time verification in React Strict Mode", async () => {
  window.history.replaceState(
    {},
    "",
    "/verify-email#token=strict-mode-token",
  );
  const fetchMock = vi.fn((input: RequestInfo | URL) =>
    Promise.resolve(
      String(input) === "/api/auth/session"
        ? sessionResponse(false)
        : new Response(
            JSON.stringify({ message: "Email підтверджено. Акаунт активовано." }),
            { status: 200 },
          ),
    ),
  );
  vi.stubGlobal("fetch", fetchMock);

  render(
    <StrictMode>
      <App />
    </StrictMode>,
  );

  expect(
    await screen.findByRole("heading", { name: "Акаунт активовано" }),
  ).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.filter(
      ([url]) => url === "/api/auth/verify-email",
    ),
  ).toHaveLength(1);
  expect(
    fetchMock.mock.calls.filter(([url]) => url === "/api/auth/session"),
  ).toHaveLength(1);
});

it("shows a controlled message when verification transport fails", async () => {
  window.history.replaceState({}, "", "/verify-email#token=network-error-token");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Network error")));

  render(<App />);

  expect(
    await screen.findByText(
      "Сервіс підтвердження недоступний. Спробуйте пізніше.",
    ),
  ).toBeInTheDocument();
});

function sessionResponse(authenticated: boolean): Response {
  return authenticated
    ? new Response(
        JSON.stringify({
          id: "8158fd82-2d50-4f4f-af31-e969bab77163",
          email: "user@example.com",
        }),
        { status: 200 },
      )
    : new Response(
        JSON.stringify({
          code: "invalid_session",
          message: "Потрібна авторизація.",
        }),
        { status: 401 },
      );
}

it("renders a password-protected Formik login form", async () => {
  window.history.replaceState({}, "", "/login");
  const fetchMock = vi.fn().mockResolvedValue(sessionResponse(false));
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(
    await screen.findByRole("heading", { name: "Увійти" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Email")).toBeInTheDocument();
  expect(screen.getByLabelText("Пароль")).toHaveAttribute("type", "password");
  expect(screen.getByRole("button", { name: "Увійти" })).toBeInTheDocument();
});

it("keeps required and email validation inside Formik without submitting", async () => {
  window.history.replaceState({}, "", "/login");
  const fetchMock = vi.fn().mockResolvedValue(sessionResponse(false));
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  await screen.findByRole("heading", { name: "Увійти" });

  fireEvent.click(screen.getByRole("button", { name: "Увійти" }));
  expect(
    await screen.findByText("Email є обов’язковим полем."),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Пароль є обов’язковим полем."),
  ).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "not-an-email" },
  });
  fireEvent.blur(screen.getByLabelText("Email"));
  expect(
    await screen.findByText("Введіть коректну email-адресу."),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("logs in, keeps the password out of the URL, and opens dashboard", async () => {
  window.history.replaceState({}, "", "/login");
  let loginWasSent = false;
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/auth/login") {
        loginWasSent = true;
        return new Response(
          JSON.stringify({
            id: "8158fd82-2d50-4f4f-af31-e969bab77163",
            email: "user@example.com",
          }),
          { status: 200 },
        );
      }
      if (url === "/api/auth/session") {
        return sessionResponse(loginWasSent);
      }
      throw new Error(`Unexpected request: ${url} ${init?.method}`);
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  await screen.findByRole("heading", { name: "Увійти" });

  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: " user@example.com " },
  });
  fireEvent.change(screen.getByLabelText("Пароль"), {
    target: { value: "secret-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Увійти" }));

  expect(
    await screen.findByRole("heading", { name: "Робочий простір" }),
  ).toBeInTheDocument();
  const loginCall = fetchMock.mock.calls.find(
    ([url]) => url === "/api/auth/login",
  );
  expect(loginCall?.[1]).toMatchObject({
    credentials: "same-origin",
    method: "POST",
    body: JSON.stringify({
      email: "user@example.com",
      password: "secret-password",
    }),
  });
  expect(
    fetchMock.mock.calls.every(
      ([url]) => !String(url).includes("secret-password"),
    ),
  ).toBe(true);
  expect(
    fetchMock.mock.calls.filter(([url]) => url === "/api/auth/session"),
  ).toHaveLength(1);
});

it.each([
  [401, "invalid_credentials", "Неправильні облікові дані."],
  [403, "unverified_account", "Підтвердьте акаунт перед входом."],
])(
  "shows the controlled login error for HTTP %i",
  async (status, code, message) => {
    window.history.replaceState({}, "", "/login");
    let sessionChecked = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/auth/session") {
          sessionChecked = true;
          return sessionResponse(false);
        }
        if (!sessionChecked) throw new Error("Login preceded session check");
        return new Response(JSON.stringify({ code, message }), { status });
      }),
    );
    render(<App />);
    await screen.findByRole("heading", { name: "Увійти" });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Пароль"), {
      target: { value: "wrong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Увійти" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  },
);

it("redirects an already authenticated user away from login", async () => {
  window.history.replaceState({}, "", "/login");
  vi.stubGlobal("fetch", vi.fn().mockImplementation(() => sessionResponse(true)));

  render(<App />);

  expect(
    await screen.findByRole("heading", { name: "Робочий простір" }),
  ).toBeInTheDocument();
});

it("redirects an anonymous dashboard visitor to login", async () => {
  window.history.replaceState({}, "", "/dashboard");
  vi.stubGlobal("fetch", vi.fn().mockImplementation(() => sessionResponse(false)));

  render(<App />);

  expect(
    await screen.findByRole("heading", { name: "Увійти" }),
  ).toBeInTheDocument();
});
