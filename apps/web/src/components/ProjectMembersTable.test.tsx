import { fireEvent, render, screen } from "@testing-library/react";
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

describe("ProjectMembersTable", () => {
  it("lists every member's email and role", () => {
    render(
      <ProjectMembersTable
        members={[
          member(),
          member({ user_id: "u2", email: "editor@example.com", role: "editor" }),
        ]}
        myRole="owner"
        actionState={{}}
        onChangeRole={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    expect(screen.getByText("owner@example.com")).toBeInTheDocument();
    expect(screen.getByText("editor@example.com")).toBeInTheDocument();
  });

  it("lets the owner change a member's role", async () => {
    const user = userEvent.setup();
    const onChangeRole = vi.fn();
    render(
      <ProjectMembersTable
        members={[member({ user_id: "u2", email: "editor@example.com", role: "editor" })]}
        myRole="owner"
        actionState={{}}
        onChangeRole={onChangeRole}
        onRemove={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole("combobox", { name: /Роль учасника editor@example.com/ }),
    );
    await user.click(screen.getByRole("option", { name: "Рецензент" }));

    expect(onChangeRole).toHaveBeenCalledWith("u2", "reviewer");
  });

  it("lets the owner remove a member", () => {
    const onRemove = vi.fn();
    const target = member({ user_id: "u2", email: "editor@example.com", role: "editor" });
    render(
      <ProjectMembersTable
        members={[target]}
        myRole="owner"
        actionState={{}}
        onChangeRole={vi.fn()}
        onRemove={onRemove}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Видалити" }));

    expect(onRemove).toHaveBeenCalledWith(target);
  });

  it("hides mutate controls for a non-owner viewer", () => {
    render(
      <ProjectMembersTable
        members={[
          member(),
          member({ user_id: "u2", email: "editor@example.com", role: "editor" }),
        ]}
        myRole="viewer"
        actionState={{}}
        onChangeRole={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "Видалити" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("never offers to remove or re-role the owner row", () => {
    render(
      <ProjectMembersTable
        members={[member()]}
        myRole="owner"
        actionState={{}}
        onChangeRole={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "Видалити" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
