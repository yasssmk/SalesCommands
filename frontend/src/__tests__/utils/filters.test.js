// frontend/src/__tests__/utils/filters.test.js
//
// 8h — the inline filter pattern's definitions: utils/filters/filterDefinitions
// (EMPTY_MEANS, restrictFilter, toQueryParams — generic, Territory-ready) and
// utils/filters/signalFilters (the signal type definitions, options derived
// from utils/signalTypes).

import { describe, it, expect } from "vitest";
import { EMPTY_MEANS, restrictFilter, toQueryParams } from "utils/filters/filterDefinitions";
import { QUALIFICATION_TYPE_FILTER, SIGNAL_TYPE_FILTER } from "utils/filters/signalFilters";
import { QUALIFICATION_SIGNAL_TYPES, SIGNAL_TYPE_SLUGS, getSignalTypeLabel } from "utils/signalTypes";

describe("signal filter definitions", () => {
  it("the type filter: every slug with its central label, repeatable signal_type, empty = all", () => {
    expect(SIGNAL_TYPE_FILTER).toMatchObject({ key: "types", param: "signal_type", label: "Type",
      multiple: true, emptyMeans: EMPTY_MEANS.ALL });
    expect(SIGNAL_TYPE_FILTER.options).toEqual(
      SIGNAL_TYPE_SLUGS.map((value) => ({ value, label: getSignalTypeLabel(value) })),
    );
  });

  it("the qualification filter: the 8 types, empty = the surface (all 8)", () => {
    expect(QUALIFICATION_TYPE_FILTER.options.map((o) => o.value)).toEqual(QUALIFICATION_SIGNAL_TYPES);
    expect(QUALIFICATION_TYPE_FILTER.emptyMeans).toBe(EMPTY_MEANS.SURFACE);
    expect(QUALIFICATION_TYPE_FILTER.param).toBe("signal_type");
  });
});

describe("restrictFilter", () => {
  it("keeps the definition, narrows the options (definition order), applies overrides", () => {
    const def = restrictFilter(SIGNAL_TYPE_FILTER, ["impact", "pain"], { emptyMeans: EMPTY_MEANS.SURFACE });
    expect(def.options.map((o) => o.value)).toEqual(["pain", "impact"]);
    expect(def).toMatchObject({ key: "types", param: "signal_type", emptyMeans: "surface" });
  });
});

describe("toQueryParams", () => {
  it("values → the server param, repeated", () => {
    expect(toQueryParams([SIGNAL_TYPE_FILTER], { types: ["pain", "people"] }))
      .toEqual({ signal_type: ["pain", "people"] });
  });

  it("empty + emptyMeans all → nothing sent (the server's all)", () => {
    expect(toQueryParams([SIGNAL_TYPE_FILTER], { types: [] })).toEqual({});
    expect(toQueryParams([SIGNAL_TYPE_FILTER], {})).toEqual({});
  });

  it("empty + emptyMeans surface → every option of the surface", () => {
    expect(toQueryParams([QUALIFICATION_TYPE_FILTER], { types: [] }))
      .toEqual({ signal_type: QUALIFICATION_SIGNAL_TYPES });
  });

  it("a value outside the definition is never sent (no dead filter)", () => {
    expect(toQueryParams([QUALIFICATION_TYPE_FILTER], { types: ["next-steps", "pain"] }))
      .toEqual({ signal_type: ["pain"] });
  });
});
