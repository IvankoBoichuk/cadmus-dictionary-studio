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

it("opens registration and shows validation errors beside fields", () => {
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

  expect(screen.getByLabelText("Email")).toHaveAttribute(
    "aria-describedby",
    "email-error",
  );
  expect(screen.getByText("Введіть коректну email-адресу.")).toBeInTheDocument();
  expect(
    screen.getByText("Пароль має містити щонайменше 12 символів."),
  ).toBeInTheDocument();
  expect(screen.getByText("Паролі не збігаються.")).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});

it("registers a user and asks them to verify email", async () => {
  window.history.replaceState({}, "", "/register");
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        status: "pending_verification",
        message: "Акаунт створено. Перевірте email, щоб активувати його.",
      }),
      { status: 201 },
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
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          errors: { email: "Ця email-адреса вже зареєстрована." },
        }),
        { status: 409 },
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
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({ message: "Email підтверджено. Акаунт активовано." }),
      { status: 200 },
    ),
  );
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(
    await screen.findByRole("heading", { name: "Акаунт активовано" }),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("/api/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: "one-time-token" }),
  });
});

it("shows the activation error returned for an unusable token", async () => {
  window.history.replaceState({}, "", "/verify-email#token=used-token");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "used",
          message: "Це посилання вже було використано.",
        }),
        { status: 400 },
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
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({ message: "Email підтверджено. Акаунт активовано." }),
      { status: 200 },
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
  expect(fetchMock).toHaveBeenCalledTimes(1);
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
