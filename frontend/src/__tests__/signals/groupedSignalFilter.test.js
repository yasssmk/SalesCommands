// frontend/src/__tests__/signals/groupedSignalFilter.test.js
//
// Client-side Qualification filter for the Activity grouped view. Mirrors the
// backend cluster-endpoint semantics: perimeter is an OR (scope=BUSINESS OR
// target_department in ids); what / dimension / contact / status are AND; a
// signal type lacking a field is excluded when that filter is active.

import { describe, it, expect } from "vitest";
import { applyGroupedFilters } from "utils/groupedSignalFilter";

const business = {
  id: "b",
  status: "PENDING",
  scope_level: "BUSINESS",
  target_department: null,
  what: "OPS",
  dimension: "TIME",
  source_context: { contacts: [{ id: "c1" }] },
};
const marketing = {
  id: "m",
  status: "PENDING",
  scope_level: "DEPARTMENT",
  target_department: { id: "3", name: "Marketing" },
  what: "DATA",
  dimension: "QUALITY",
  source_context: { contacts: [{ id: "c2" }] },
};
const finance = {
  id: "f",
  status: "VALIDATED",
  scope_level: "DEPARTMENT",
  target_department: { id: "5", name: "Finance" },
  what: "GROWTH",
  dimension: "COST",
  source_context: { contacts: [{ id: "c3" }] },
};
// A tech-stack signal has no what / dimension / scope_level / target_department.
const tech = {
  id: "t",
  status: "PENDING",
  _signalType: "tech-stack",
  source_context: { contacts: [{ id: "c1" }] },
};
const rejected = { ...business, id: "r", status: "REJECTED" };

const ALL = [business, marketing, finance, tech, rejected];
const ids = (rows) => rows.map((s) => s.id);

describe("applyGroupedFilters — perimeter (OR)", () => {
  it("[Business, Marketing] keeps scope=BUSINESS OR target=Marketing", () => {
    const out = applyGroupedFilters(ALL, { perimeter: ["BUSINESS", "3"] });
    // business (BUSINESS) + marketing (dept 3); finance/tech excluded.
    expect(ids(out).sort()).toEqual(["b", "m"]);
  });

  it("[Business] alone keeps only scope=BUSINESS", () => {
    const out = applyGroupedFilters(ALL, { perimeter: ["BUSINESS"] });
    expect(ids(out)).toEqual(["b"]);
  });

  it("[dept] alone keeps only that department (Business excluded)", () => {
    const out = applyGroupedFilters(ALL, { perimeter: ["3"] });
    expect(ids(out)).toEqual(["m"]);
  });
});

describe("applyGroupedFilters — subject axes + type without field", () => {
  it("what=[DATA] keeps only DATA signals; a type without `what` is excluded", () => {
    const out = applyGroupedFilters(ALL, { whats: ["DATA"] });
    expect(ids(out)).toEqual(["m"]); // tech (no what) excluded
  });

  it("dimension=[QUALITY] keeps only QUALITY signals", () => {
    const out = applyGroupedFilters(ALL, { dimensions: ["QUALITY"] });
    expect(ids(out)).toEqual(["m"]);
  });
});

describe("applyGroupedFilters — contact (source, AND)", () => {
  it("contact=[c2] keeps signals whose source contacts include c2", () => {
    const out = applyGroupedFilters(ALL, { contacts: ["c2"] });
    expect(ids(out)).toEqual(["m"]);
  });
});

describe("applyGroupedFilters — status default + AND", () => {
  it("defaults to pending+validated (REJECTED excluded)", () => {
    const out = applyGroupedFilters(ALL, {});
    expect(ids(out)).not.toContain("r");
  });

  it("includes REJECTED only when explicitly selected", () => {
    const out = applyGroupedFilters(ALL, { statuses: ["REJECTED"] });
    expect(ids(out)).toEqual(["r"]);
  });

  it("perimeter AND what across families", () => {
    // Business perimeter AND what=DATA → business is OPS, so nothing matches.
    const out = applyGroupedFilters(ALL, {
      perimeter: ["BUSINESS"],
      whats: ["DATA"],
    });
    expect(out).toEqual([]);
  });
});
