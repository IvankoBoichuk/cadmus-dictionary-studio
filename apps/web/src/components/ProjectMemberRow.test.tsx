import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProjectMemberRow } from "./ProjectMemberRow";

function renderRow(ui: React.ReactElement) {
  return render(
    <table>
      <tbody>{ui}</tbody>
    </table>,
  );
}

describe("ProjectMemberRow", () => {
  it("keeps submit disabled until an email is entered, then invites", async () => {
    const onAdd = vi.fn().mockResolvedValue(true);
    const onDone = vi.fn();
    renderRow(
      <ProjectMemberRow actionState={undefined} onAdd={onAdd} onDone={onDone} />,
    );

    expect(screen.getByRole("button", { name: "Запросити" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Пошта"), {
      target: { value: "invitee@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Запросити" }));

    await waitFor(() =>
      expect(onAdd).toHaveBeenCalledWith("invitee@example.com", "viewer"),
    );
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
  });

  it("stays open and shows the error when the invite fails", async () => {
    const onAdd = vi.fn().mockResolvedValue(false);
    const onDone = vi.fn();
    renderRow(
      <ProjectMemberRow
        actionState={{ pending: false, error: "Користувача не знайдено." }}
        onAdd={onAdd}
        onDone={onDone}
      />,
    );

    fireEvent.change(screen.getByLabelText("Пошта"), {
      target: { value: "ghost@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Запросити" }));

    await waitFor(() => expect(onAdd).toHaveBeenCalled());
    expect(onDone).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Користувача не знайдено.");
  });

  it("cancels without inviting", () => {
    const onAdd = vi.fn();
    const onDone = vi.fn();
    renderRow(
      <ProjectMemberRow actionState={undefined} onAdd={onAdd} onDone={onDone} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Скасувати" }));

    expect(onDone).toHaveBeenCalledTimes(1);
    expect(onAdd).not.toHaveBeenCalled();
  });
});
