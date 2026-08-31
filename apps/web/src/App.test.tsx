import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { App } from "./App";

afterEach(() => {
  window.history.replaceState({}, "", "/");
  vi.unstubAllGlobals();
});

it("renders the landing page with the offer and benefits sections", () => {
  render(<App />);

  expect(
    screen.getByRole("heading", { name: "Cadmus Dictionary Studio" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Cadmus — головна" })).toHaveAttribute(
    "href",
    "/",
  );
  expect(
    screen.getByRole("heading", { name: "Шлях від скану до даних" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Чому команди обирають Cadmus" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "API" }),
  ).not.toBeInTheDocument();
});

it("shows the system status on the /status page", async () => {
  window.history.replaceState({}, "", "/status");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    ),
  );

  render(<App />);

  expect(
    screen.getByRole("heading", { level: 1, name: "Стан системи" }),
  ).toBeInTheDocument();
  await waitFor(() =>
    expect(screen.getByRole("status")).toHaveTextContent("Доступний"),
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
  expect(screen.getByLabelText("Email")).toHaveAccessibleDescription(
    "Введіть коректну email-адресу.",
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
  expect(screen.getByLabelText("Email")).toHaveAccessibleDescription(
    "Ця email-адреса вже зареєстрована.",
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
  expect(screen.getByRole("link", { name: "Продовжити з Google" })).toHaveAttribute(
    "href",
    "/api/auth/google/start",
  );
});

it("shows a controlled error banner when Google sign-in fails", async () => {
  window.history.replaceState({}, "", "/login?error=google_auth_failed");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sessionResponse(false)));

  render(<App />);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Не вдалося увійти через Google.",
  );
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
      if (url === "/api/dictionaries") {
        return new Response("[]", { status: 200 });
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
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) =>
      String(input) === "/api/dictionaries"
        ? new Response("[]", { status: 200 })
        : sessionResponse(true),
    ),
  );

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

it("logs out from an authenticated page and redirects to login", async () => {
  window.history.replaceState({}, "", "/dashboard");
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === "/api/auth/session") return sessionResponse(true);
      if (String(input) === "/api/dictionaries") {
        return new Response("[]", { status: 200 });
      }
      if (String(input) === "/api/auth/logout") {
        return new Response(JSON.stringify({ message: "Ви вийшли із системи." }), {
          status: 200,
        });
      }
      throw new Error(`Unexpected request: ${String(input)} ${init?.method}`);
    },
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  await screen.findByRole("heading", { name: "Робочий простір" });
  fireEvent.click(screen.getByRole("button", { name: "Вийти" }));

  expect(await screen.findByRole("heading", { name: "Увійти" })).toBeInTheDocument();
  expect(window.location.pathname).toBe("/login");
  const logoutCall = fetchMock.mock.calls.find(
    ([url]) => String(url) === "/api/auth/logout",
  );
  expect(logoutCall?.[1]).toMatchObject({
    credentials: "same-origin",
    method: "POST",
  });
});

it("blocks forgot-password submission for an invalid email without calling fetch", async () => {
  window.history.replaceState({}, "", "/forgot-password");
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "invalid" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Надіслати інструкції" }));

  expect(
    await screen.findByText("Введіть коректну email-адресу."),
  ).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(([url]) => url === "/api/auth/forgot-password"),
  ).toBe(false);
});

it("shows the same neutral confirmation for forgot-password regardless of account existence", async () => {
  window.history.replaceState({}, "", "/forgot-password");
  const neutralMessage =
    "Якщо такий email зареєстровано, ми надіслали інструкції для відновлення пароля.";
  const fetchMock = vi.fn((input: RequestInfo | URL) =>
    String(input) === "/api/auth/session"
      ? Promise.resolve(sessionResponse(false))
      : Promise.resolve(
          new Response(JSON.stringify({ message: neutralMessage }), { status: 200 }),
        ),
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "unknown@example.com" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Надіслати інструкції" }));

  expect(
    await screen.findByRole("heading", { name: "Перевірте email" }),
  ).toBeInTheDocument();
  expect(screen.getByText(neutralMessage)).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("/api/auth/forgot-password", {
    credentials: "same-origin",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "unknown@example.com" }),
  });
});

it("shows an invalid-link state for reset-password with no token and never calls fetch", async () => {
  window.history.replaceState({}, "", "/reset-password");
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(
    await screen.findByRole("heading", { name: "Не вдалося відновити пароль" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Надіслати новий запит" }),
  ).toHaveAttribute("href", "/forgot-password");
  expect(
    fetchMock.mock.calls.some(([url]) => url === "/api/auth/reset-password"),
  ).toBe(false);
});

it("blocks reset-password submission for a weak or mismatched password", async () => {
  window.history.replaceState({}, "", "/reset-password#token=one-time-token");
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  fireEvent.change(screen.getByLabelText("Новий пароль"), {
    target: { value: "short" },
  });
  fireEvent.change(screen.getByLabelText("Підтвердження пароля"), {
    target: { value: "different" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Змінити пароль" }));

  expect(
    await screen.findByText("Пароль має містити щонайменше 12 символів."),
  ).toBeInTheDocument();
  expect(screen.getByText("Паролі не збігаються.")).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(([url]) => url === "/api/auth/reset-password"),
  ).toBe(false);
});

it("resets the password, keeps the token out of the URL, and links to login", async () => {
  window.history.replaceState({}, "", "/reset-password#token=one-time-token");
  const fetchMock = vi.fn((input: RequestInfo | URL) =>
    String(input) === "/api/auth/session"
      ? Promise.resolve(sessionResponse(false))
      : Promise.resolve(
          new Response(
            JSON.stringify({ message: "Пароль змінено. Тепер ви можете увійти." }),
            { status: 200 },
          ),
        ),
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  fireEvent.change(screen.getByLabelText("Новий пароль"), {
    target: { value: "new-long-enough-password" },
  });
  fireEvent.change(screen.getByLabelText("Підтвердження пароля"), {
    target: { value: "new-long-enough-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Змінити пароль" }));

  const heading = await screen.findByRole("heading", { name: "Пароль змінено" });
  expect(heading).toBeInTheDocument();
  const resultCard = heading.closest("section") as HTMLElement;
  expect(within(resultCard).getByRole("link", { name: "Увійти" })).toHaveAttribute(
    "href",
    "/login",
  );
  expect(fetchMock).toHaveBeenCalledWith("/api/auth/reset-password", {
    credentials: "same-origin",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      token: "one-time-token",
      new_password: "new-long-enough-password",
      new_password_confirmation: "new-long-enough-password",
    }),
  });
  expect(
    fetchMock.mock.calls.every(
      ([url]) =>
        !String(url).includes("one-time-token") &&
        !String(url).includes("new-long-enough-password"),
    ),
  ).toBe(true);
});

it("offers a new reset request for an expired or used token", async () => {
  window.history.replaceState({}, "", "/reset-password#token=used-token");
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      String(input) === "/api/auth/session"
        ? Promise.resolve(sessionResponse(false))
        : Promise.resolve(
            new Response(
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
  fireEvent.change(screen.getByLabelText("Новий пароль"), {
    target: { value: "new-long-enough-password" },
  });
  fireEvent.change(screen.getByLabelText("Підтвердження пароля"), {
    target: { value: "new-long-enough-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Змінити пароль" }));

  expect(
    await screen.findByRole("heading", { name: "Не вдалося відновити пароль" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Це посилання вже було використано.")).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Надіслати новий запит" }),
  ).toHaveAttribute("href", "/forgot-password");
});

function dictionaryListEntry(overrides: Record<string, unknown> = {}) {
  return {
    id: "33333333-3333-3333-3333-333333333333",
    status: "draft",
    title: "Словник української мови",
    description: null,
    dictionary_type: null,
    publisher: null,
    publication_year: null,
    edition: null,
    isbn: null,
    digital_source: null,
    legal_status: null,
    license_type: null,
    permission_reference: null,
    rights_note: null,
    contributors: [],
    language_codes: [],
    created_at: "2026-08-16T12:00:00Z",
    updated_at: "2026-08-16T12:00:00Z",
    missing_required_fields: [],
    source: {
      original_filename: "dictionary.pdf",
      mime_type: "application/pdf",
      byte_size: 2048,
      page_count: 2,
      checksum_sha256: "a".repeat(64),
      uploaded_at: "2026-08-16T12:00:00Z",
      inspection_status: "verified",
      pages_status: "completed",
    },
    ...overrides,
  };
}

it("shows a thumbnail image once page splitting has completed", async () => {
  window.history.replaceState({}, "", "/dictionaries");
  const entry = dictionaryListEntry();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/auth/session") return sessionResponse(true);
      if (String(input) === "/api/dictionaries") {
        return new Response(JSON.stringify([entry]), { status: 200 });
      }
      throw new Error(`Unexpected request: ${String(input)}`);
    }),
  );

  render(<App />);

  expect(
    await screen.findByRole("heading", { name: "Словник української мови" }),
  ).toBeInTheDocument();
  const image = screen.getByRole("presentation") as HTMLImageElement;
  expect(image.src).toContain(`/api/dictionaries/${entry.id}/thumbnail`);
});

it("shows a placeholder instead of a thumbnail while pages are still splitting", async () => {
  window.history.replaceState({}, "", "/dictionaries");
  const entry = dictionaryListEntry({
    source: {
      original_filename: "dictionary.pdf",
      mime_type: "application/pdf",
      byte_size: 2048,
      page_count: null,
      checksum_sha256: "a".repeat(64),
      uploaded_at: "2026-08-16T12:00:00Z",
      inspection_status: "verified",
      pages_status: "pending",
    },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/auth/session") return sessionResponse(true);
      if (String(input) === "/api/dictionaries") {
        return new Response(JSON.stringify([entry]), { status: 200 });
      }
      throw new Error(`Unexpected request: ${String(input)}`);
    }),
  );

  render(<App />);

  await screen.findByRole("heading", { name: "Словник української мови" });
  expect(screen.getByText("Розбивається на сторінки…")).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});

it("deletes a dictionary after confirmation and removes it from the list", async () => {
  window.history.replaceState({}, "", "/dictionaries");
  const entry = dictionaryListEntry();
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  let deleteCalled = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === "/api/auth/session") return sessionResponse(true);
      if (String(input) === "/api/dictionaries") {
        return new Response(JSON.stringify(deleteCalled ? [] : [entry]), {
          status: 200,
        });
      }
      if (String(input) === `/api/dictionaries/${entry.id}` && init?.method === "DELETE") {
        deleteCalled = true;
        return new Response(null, { status: 204 });
      }
      throw new Error(`Unexpected request: ${String(input)} ${init?.method}`);
    }),
  );

  render(<App />);
  await screen.findByRole("heading", { name: "Словник української мови" });
  fireEvent.click(screen.getByRole("button", { name: "Видалити" }));

  await waitFor(() => expect(deleteCalled).toBe(true));
  await waitFor(() =>
    expect(
      screen.queryByRole("heading", { name: "Словник української мови" }),
    ).not.toBeInTheDocument(),
  );
  confirmSpy.mockRestore();
});

it("keeps the dictionary when the delete confirmation is dismissed", async () => {
  window.history.replaceState({}, "", "/dictionaries");
  const entry = dictionaryListEntry();
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input) === "/api/auth/session") return sessionResponse(true);
    if (String(input) === "/api/dictionaries") {
      return new Response(JSON.stringify([entry]), { status: 200 });
    }
    throw new Error(`Unexpected request: ${String(input)} ${init?.method}`);
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  await screen.findByRole("heading", { name: "Словник української мови" });
  fireEvent.click(screen.getByRole("button", { name: "Видалити" }));

  expect(confirmSpy).toHaveBeenCalled();
  expect(
    fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE"),
  ).toBe(false);
  expect(
    screen.getByRole("heading", { name: "Словник української мови" }),
  ).toBeInTheDocument();
  confirmSpy.mockRestore();
});

it("keeps the authenticated state and reports an unconfirmed logout", async () => {
  window.history.replaceState({}, "", "/dashboard");
  let logoutAttempts = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/auth/session") return sessionResponse(true);
      if (String(input) === "/api/dictionaries") {
        return new Response("[]", { status: 200 });
      }
      if (String(input) === "/api/auth/logout") {
        logoutAttempts += 1;
        throw new TypeError("network unavailable");
      }
      throw new Error(`Unexpected request: ${String(input)}`);
    }),
  );

  render(<App />);
  await screen.findByRole("heading", { name: "Робочий простір" });
  fireEvent.click(screen.getByRole("button", { name: "Вийти" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Не вдалося підтвердити вихід із системи",
  );
  expect(screen.getByRole("heading", { name: "Робочий простір" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Вийти" })).toBeEnabled();
  expect(window.location.pathname).toBe("/dashboard");
  expect(logoutAttempts).toBe(1);
});
