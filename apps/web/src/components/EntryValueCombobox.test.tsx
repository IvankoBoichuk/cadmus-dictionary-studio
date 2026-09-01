import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { EntryValueCombobox } from "./EntryValueCombobox";

function Harness({
  items,
  onChange,
}: {
  items: string[];
  onChange: (value: string) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <EntryValueCombobox
      label="Скорочення"
      value={value}
      items={items}
      onChange={(next) => {
        setValue(next);
        onChange(next);
      }}
    />
  );
}

describe("EntryValueCombobox", () => {
  it("offers the reference list as datalist options", () => {
    render(<Harness items={["розм.", "заст."]} onChange={vi.fn()} />);

    const input = screen.getByLabelText("Скорочення");
    const listId = input.getAttribute("list");
    const list = document.getElementById(listId!) as HTMLDataListElement;
    expect(
      [...list.querySelectorAll("option")].map((option) => option.value),
    ).toEqual(["розм.", "заст."]);
  });

  it("accepts a freely typed value that is not in the list", () => {
    const onChange = vi.fn();
    render(<Harness items={["розм."]} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText("Скорочення"), {
      target: { value: "власне" },
    });

    expect(onChange).toHaveBeenLastCalledWith("власне");
    expect(screen.getByLabelText("Скорочення")).toHaveValue("власне");
  });
});
