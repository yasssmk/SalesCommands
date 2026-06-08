// frontend/src/__tests__/signals/signalValidationRules.test.js

import { describe, it, expect } from "vitest";
import {
  getRequiredFields,
  getMissingFields,
} from "sections/activities/signals/signalValidationRules";

describe("getRequiredFields", () => {
  it("returns pain required fields", () => {
    const fields = getRequiredFields("pain");
    const keys = fields.map((f) => f.key);
    expect(keys).toEqual(["what", "dimension", "summary"]);
  });

  it("returns objective required fields", () => {
    const fields = getRequiredFields("objective");
    const keys = fields.map((f) => f.key);
    expect(keys).toEqual(["what", "dimension", "scope_level", "summary"]);
  });

  it("returns impact required fields", () => {
    const fields = getRequiredFields("impact");
    const keys = fields.map((f) => f.key);
    expect(keys).toEqual([
      "what",
      "dimension",
      "scope_level",
      "impact_type",
      "summary",
    ]);
  });

  it("returns tech-stack required fields", () => {
    const fields = getRequiredFields("tech-stack");
    expect(fields).toEqual([
      { key: "tech_catalog_entry", label: "Tech catalog entry" },
    ]);
  });

  it("returns blockers required fields", () => {
    const fields = getRequiredFields("blockers");
    expect(fields).toEqual([{ key: "summary", label: "Summary" }]);
  });

  it("returns next-steps required fields", () => {
    const fields = getRequiredFields("next-steps");
    const keys = fields.map((f) => f.key);
    expect(keys).toEqual(["suggested_title", "suggested_activity_type"]);
  });

  it("returns empty array for unknown type", () => {
    expect(getRequiredFields("unknown")).toEqual([]);
  });

  it("returns empty array for null", () => {
    expect(getRequiredFields(null)).toEqual([]);
  });
});

describe("getMissingFields", () => {
  it("returns empty array when signal is null", () => {
    expect(getMissingFields(null, "pain")).toEqual([]);
  });

  it("returns empty array when signalType is null", () => {
    expect(getMissingFields({}, null)).toEqual([]);
  });

  it("returns all fields when signal is empty object", () => {
    const missing = getMissingFields({}, "pain");
    expect(missing).toHaveLength(3);
    expect(missing.map((f) => f.key)).toEqual(["what", "dimension", "summary"]);
  });

  it("returns only missing fields", () => {
    const signal = { what: "DATA", dimension: "TIME" };
    const missing = getMissingFields(signal, "pain");
    expect(missing).toHaveLength(1);
    expect(missing[0].key).toBe("summary");
  });

  it("returns empty array when all fields present", () => {
    const signal = { what: "DATA", dimension: "TIME", summary: "Some pain" };
    expect(getMissingFields(signal, "pain")).toEqual([]);
  });

  it("treats empty string as missing", () => {
    const signal = { what: "DATA", dimension: "TIME", summary: "" };
    const missing = getMissingFields(signal, "pain");
    expect(missing).toHaveLength(1);
    expect(missing[0].key).toBe("summary");
  });

  it("treats null value as missing", () => {
    const signal = { what: "DATA", dimension: null, summary: "Pain" };
    const missing = getMissingFields(signal, "pain");
    expect(missing).toHaveLength(1);
    expect(missing[0].key).toBe("dimension");
  });

  it("tech-stack: missing when no tech_catalog_entry and no pending_tech_name", () => {
    const signal = {};
    const missing = getMissingFields(signal, "tech-stack");
    expect(missing).toHaveLength(1);
    expect(missing[0].key).toBe("tech_catalog_entry");
  });

  it("tech-stack: not missing when metadata.pending_tech_name present", () => {
    const signal = { metadata: { pending_tech_name: "Notion" } };
    expect(getMissingFields(signal, "tech-stack")).toEqual([]);
  });

  it("tech-stack: not missing when tech_catalog_entry present", () => {
    const signal = { tech_catalog_entry: { id: "t1" } };
    expect(getMissingFields(signal, "tech-stack")).toEqual([]);
  });

  it("blockers: missing when no summary", () => {
    const missing = getMissingFields({}, "blockers");
    expect(missing).toHaveLength(1);
    expect(missing[0].key).toBe("summary");
  });

  it("blockers: complete when summary present", () => {
    expect(getMissingFields({ summary: "Blocked" }, "blockers")).toEqual([]);
  });
});
