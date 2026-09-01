import { describe, expect, it } from "vitest";

import { diffSchemas, flattenSchema, parseSchemaFields } from "./schemaDiff";

const NODE = (
  name: string,
  overrides: Partial<{
    role: string;
    type: string;
    options: string[];
    repeatable: boolean;
    required: boolean;
    children: unknown[];
  }> = {},
) => ({
  name,
  role: "other",
  type: "string",
  repeatable: false,
  required: false,
  children: [],
  ...overrides,
});

describe("parseSchemaFields", () => {
  it("tolerates missing/partial data", () => {
    expect(parseSchemaFields(null)).toEqual([]);
    expect(parseSchemaFields({ fields: "nope" })).toEqual([]);
    const [node] = parseSchemaFields({ fields: [{ name: "x" }] });
    expect(node).toMatchObject({
      name: "x",
      role: "",
      type: "",
      options: [],
      repeatable: false,
      children: [],
    });
  });

  it("reads enum options, dropping non-strings", () => {
    const [node] = parseSchemaFields({
      fields: [{ name: "g", type: "enum", options: ["ч.", 3, "ж."] }],
    });
    expect(node?.options).toEqual(["ч.", "ж."]);
  });
});

describe("flattenSchema", () => {
  it("keys nodes by their dotted name path", () => {
    const flat = flattenSchema({
      fields: [NODE("meaning", { children: [NODE("example")] })],
    });
    expect([...flat.keys()]).toEqual(["meaning", "meaning.example"]);
    expect(flat.get("meaning.example")?.depth).toBe(1);
  });
});

describe("diffSchemas", () => {
  it("reports added, removed, changed and unchanged nodes", () => {
    const base = {
      fields: [
        NODE("headword", { role: "headword" }),
        NODE("meaning", {
          type: "group",
          children: [NODE("example", { role: "example" })],
        }),
      ],
    };
    const compare = {
      fields: [
        NODE("headword", { role: "headword" }),
        NODE("meaning", {
          type: "group",
          required: true,
          children: [NODE("synonym", { role: "synonym" })],
        }),
      ],
    };

    const rows = diffSchemas(base, compare);
    const byPath = new Map(rows.map((row) => [row.path, row]));

    expect(byPath.get("headword")?.kind).toBe("unchanged");
    expect(byPath.get("meaning")?.kind).toBe("changed");
    expect(byPath.get("meaning")?.changes).toEqual([
      { field: "required", from: false, to: true },
    ]);
    expect(byPath.get("meaning.example")?.kind).toBe("removed");
    expect(byPath.get("meaning.synonym")?.kind).toBe("added");
  });

  it("reports a change to an enum's options list", () => {
    const base = { fields: [NODE("g", { type: "enum", options: ["ч.", "ж."] })] };
    const compare = {
      fields: [NODE("g", { type: "enum", options: ["ч.", "ж.", "с."] })],
    };
    const [row] = diffSchemas(base, compare);
    expect(row?.kind).toBe("changed");
    expect(row?.changes).toEqual([
      { field: "options", from: "ч. · ж.", to: "ч. · ж. · с." },
    ]);
  });

  it("treats two identical definitions as all-unchanged", () => {
    const def = { fields: [NODE("a"), NODE("b")] };
    const rows = diffSchemas(def, structuredClone(def));
    expect(rows.every((row) => row.kind === "unchanged")).toBe(true);
  });
});
