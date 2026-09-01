import { useId } from "react";

/**
 * A free-text input backed by a native `<datalist>` of suggestions from one of
 * the dictionary's reference lists (BH-29 abbreviations / BH-30 settlements).
 * The value is never constrained — a "not in the list" hint is the caller's
 * responsibility (BH-148, soft validation).
 */
export function EntryValueCombobox({
  label,
  value,
  onChange,
  items,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  items: string[];
  placeholder?: string;
}) {
  const listId = useId();
  return (
    <label className="grid gap-1 text-[0.82rem]">
      {label}
      <input
        className="rounded-[0.4rem] border border-input px-2 py-1"
        list={listId}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
      <datalist id={listId}>
        {items.map((item) => (
          <option key={item} value={item} />
        ))}
      </datalist>
    </label>
  );
}
