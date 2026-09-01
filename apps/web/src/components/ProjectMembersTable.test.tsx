import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { MemberResponse } from "../api";
import { ProjectMembersTable } from "./ProjectMembersTable";

function member(overrides: Partial<MemberResponse> = {}): MemberResponse {
  return {
    user_id: "22222222-2222-2222-2222-222222222222",
    email: "owner@example.com",
    role: "owner",
    created_at: "2026-08-25T00:00:00Z",
    updated_at: "2026-08-25T00:00:00Z",
    ...overrides,
  };
}

function renderTable(props: Partial<Parameters<typeof ProjectMembersTable>[0]> = {}) {
  return render(
    <ProjectMembersTable
      members={[member()]}
      myRole="owner"
      actionState={{}}
      onChangeRole={vi.fn()}
      onRemove={vi.fn()}
      onAdd={vi.fn()}
      {...props}
    />,
  );
}

describe("ProjectMembersTable", () => {
  it("lists every member's email and role", () => {
    renderTable({
      members: [
        member(),
        member({ user_id: "u2", email: "editor@example.com", role: "editor" }),
      ],
    });

    expect(screen.getByText("owner@example.com")).toBeInTheDocument();
    expect(screen.getByText("editor@example.com")).toBeInTheDocument();
  });

  it("lets the owner change a member's role", async () => {
    const user = userEvent.setup();
    const onChangeRole = vi.fn();
    renderTable({
      members: [
        member({ user_id: "u2", email: "editor@example.com", role: "editor" }),
      ],
      onChangeRole,
    });

    await user.click(
      screen.getByRole("combobox", { name: /Роль учасника editor@example.com/ }),
    );
    await user.click(screen.getByRole("option", { name: "Рецензент" }));

    expect(onChangeRole).toHaveBeenCalledWith("u2", "reviewer");
  });

  it("lets the owner remove a member", () => {
    const onRemove = vi.fn();
    const target = member({
      user_id: "u2",
      email: "editor@example.com",
      role: "editor",
    });
    renderTable({ members: [target], onRemove });

    fireEvent.click(screen.getByRole("button", { name: "Видалити" }));

    expect(onRemove).toHaveBeenCalledWith(target);
  });

  it("hides mutate controls for a non-owner viewer", () => {
    renderTable({
      members: [
        member(),
        member({ user_id: "u2", email: "editor@example.com", role: "editor" }),
      ],
      myRole: "viewer",
    });

    expect(
      screen.queryByRole("button", { name: "Видалити" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Запросити учасника" }),
    ).not.toBeInTheDocument();
  });

  it("never offers to remove or re-role the owner row", () => {
    renderTable({ members: [member()] });

    expect(
      screen.queryByRole("button", { name: "Видалити" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("reveals the inline invite row from the footer + button", async () => {
    const onAdd = vi.fn().mockResolvedValue(true);
    renderTable({ onAdd });

    fireEvent.click(screen.getByRole("button", { name: "Запросити учасника" }));

    const email = screen.getByLabelText("Пошта");
    fireEvent.change(email, { target: { value: "new@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Запросити" }));

    await waitFor(() =>
      expect(onAdd).toHaveBeenCalledWith("new@example.com", "viewer"),
    );
    await waitFor(() =>
      expect(
        screen.queryByLabelText("Пошта"),
      ).not.toBeInTheDocument(),
    );
  });
});
