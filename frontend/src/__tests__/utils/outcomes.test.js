// frontend/src/__tests__/utils/outcomes.test.js
//
// O-1 — the unified outcome source of truth: the 11 backend ActivityOutcome
// values, their labels + palette roles, and the PO-validated type→outcomes map
// consumed by getOutcomesForType(activityType).

import { describe, it, expect } from "vitest";
import {
  OUTCOME_VALUES,
  OUTCOME_META,
  getOutcomesForType,
} from "utils/outcomes";

const ALL_11 = [
  "SUCCESSFUL",
  "NO_ANSWER",
  "CALLBACK_REQUESTED",
  "NOT_INTERESTED",
  "WRONG_CONTACT",
  "MEETING_SCHEDULED",
  "FOLLOW_UP_NEEDED",
  "UNSUBSCRIBE_OPTOUT",
  "WRONG_EMAIL",
  "INVALID_PHONE_NUMBER",
  "OTHER",
];

describe("outcomes — unified source aligns with the 11 backend values", () => {
  it("exposes exactly the 11 backend ActivityOutcome values", () => {
    expect([...OUTCOME_VALUES].sort()).toEqual([...ALL_11].sort());
  });

  it("has a label and a palette role for every outcome", () => {
    ALL_11.forEach((o) => {
      expect(OUTCOME_META[o]).toBeTruthy();
      expect(typeof OUTCOME_META[o].label).toBe("string");
      expect(OUTCOME_META[o].label.length).toBeGreaterThan(0);
      expect(typeof OUTCOME_META[o].role).toBe("string");
    });
  });
});

// The PO-validated table, transcribed as the expected SET per type.
const EXPECTED = {
  CALL: [
    "SUCCESSFUL", "NOT_INTERESTED", "MEETING_SCHEDULED", "FOLLOW_UP_NEEDED", "OTHER",
    "NO_ANSWER", "CALLBACK_REQUESTED", "WRONG_CONTACT", "INVALID_PHONE_NUMBER", "UNSUBSCRIBE_OPTOUT",
  ],
  MEETING: [
    "SUCCESSFUL", "NOT_INTERESTED", "MEETING_SCHEDULED", "FOLLOW_UP_NEEDED", "OTHER",
    "NO_ANSWER", "WRONG_CONTACT",
  ],
  EMAIL: [
    "SUCCESSFUL", "NOT_INTERESTED", "MEETING_SCHEDULED", "FOLLOW_UP_NEEDED", "OTHER",
    "NO_ANSWER", "CALLBACK_REQUESTED", "WRONG_CONTACT", "WRONG_EMAIL", "UNSUBSCRIBE_OPTOUT",
  ],
  LINKEDIN: [
    "SUCCESSFUL", "NOT_INTERESTED", "MEETING_SCHEDULED", "FOLLOW_UP_NEEDED", "OTHER",
    "NO_ANSWER", "CALLBACK_REQUESTED", "WRONG_CONTACT", "UNSUBSCRIBE_OPTOUT",
  ],
  TASK: [
    "SUCCESSFUL", "NOT_INTERESTED", "MEETING_SCHEDULED", "FOLLOW_UP_NEEDED", "OTHER",
    "NO_ANSWER",
  ],
  DEMO: [
    "SUCCESSFUL", "NOT_INTERESTED", "MEETING_SCHEDULED", "FOLLOW_UP_NEEDED", "OTHER",
    "NO_ANSWER", "CALLBACK_REQUESTED", "WRONG_CONTACT", "WRONG_EMAIL", "INVALID_PHONE_NUMBER",
  ],
};

describe("getOutcomesForType — the PO-validated type→outcomes map", () => {
  Object.entries(EXPECTED).forEach(([type, expected]) => {
    it(`${type} → exactly its validated set`, () => {
      const got = getOutcomesForType(type);
      expect([...got].sort()).toEqual([...expected].sort());
      // every returned value is a real outcome
      got.forEach((o) => expect(OUTCOME_VALUES).toContain(o));
    });
  });

  it("OTHER activity type → the common base fallback (no NO_ANSWER)", () => {
    expect([...getOutcomesForType("OTHER")].sort()).toEqual(
      ["SUCCESSFUL", "NOT_INTERESTED", "MEETING_SCHEDULED", "FOLLOW_UP_NEEDED", "OTHER"].sort(),
    );
  });

  it("unknown/empty type → the same safe base fallback", () => {
    expect([...getOutcomesForType(undefined)].sort()).toEqual(
      ["SUCCESSFUL", "NOT_INTERESTED", "MEETING_SCHEDULED", "FOLLOW_UP_NEEDED", "OTHER"].sort(),
    );
  });

  it("returns a stable, deterministic order (idempotent)", () => {
    expect(getOutcomesForType("CALL")).toEqual(getOutcomesForType("CALL"));
  });
});
