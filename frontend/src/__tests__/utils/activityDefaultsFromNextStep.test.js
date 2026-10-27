// frontend/src/__tests__/utils/activityDefaultsFromNextStep.test.js
//
// Sprint Next steps 5.8d (2/3) — activityDefaultsFromNextStep(nextStep, context):
// the SINGLE source of the activity pre-fill from a next step (2.2b), used by
// ActivityModal and the coque creation drawer.
//   * title, type (the entry point's type wins), date by D6, objective +
//     success criterion, description = topics (unchanged 2.2b rules);
//   * contacts: the next step's contacts + its People's contacts (2.2b);
//   * names cited (PO rule 5.8c): for MEETING / CALL / EMAIL, the account
//     contacts the server matched WITHOUT ambiguity (context.citedContacts,
//     GET cited-contacts — the TD-279 rule) are added, the other names are
//     "Mentioned" (a reminder); for the OTHER types the names cited are added
//     to the description ("Mentioned: …");
//   * internal names → the description ("Internal: …"), every type.

import { describe, it, expect } from "vitest";

import { activityDefaultsFromNextStep } from "utils/activityTypes";

const LAURENT = { id: "c-9", first_name: "Laurent", last_name: "Dubois" };
const THOMAS = { id: "c-1", first_name: "Thomas", last_name: "Lefèvre" };

const NS = {
  id: "ns-1",
  suggested_title: "Security review",
  suggested_activity_type: "MEETING",
  suggested_due_date: "2026-11-03",
  suggested_objective: "Unblock the review",
  suggested_success_criterion: "The DSI signs",
  suggested_topics: "DPA, SOC 2",
  suggested_contacts: [],
  suggested_people: [{ id: "p-1", full_name: "Thomas Lefèvre", target_contact: THOMAS }],
  suggested_people_names: ["Laurent", "Marc"],
  suggested_internal_names: ["Sophie"],
};

const CITED = [
  { name: "Thomas Lefèvre", contact: THOMAS },
  { name: "Laurent", contact: LAURENT },
  { name: "Marc", contact: null },
];

describe("activityDefaultsFromNextStep (5.8d)", () => {
  it("2.2b fields: title, type, D6 date, objective + criterion", () => {
    const d = activityDefaultsFromNextStep(NS, {});
    expect(d.title).toBe("Security review");
    expect(d.activity_type).toBe("MEETING");
    expect(d.scheduled_date).toBe("2026-11-03");
    expect(d.due_date).toBeNull();
    expect(d.call_to_action).toBe("Unblock the review\n\nSuccess criterion: The DSI signs");
  });

  it("the entry point's type wins, and drives D6", () => {
    const d = activityDefaultsFromNextStep(NS, { activityType: "TASK" });
    expect(d.activity_type).toBe("TASK");
    expect(d.scheduled_date).toBeNull();
    expect(d.due_date).toBe("2026-11-03");
  });

  it("MEETING / CALL / EMAIL: the matched account contacts join, the others are Mentioned", () => {
    for (const activityType of ["MEETING", "CALL", "EMAIL"]) {
      const d = activityDefaultsFromNextStep(NS, { activityType, citedContacts: CITED });
      expect(d.contacts.map((c) => c.id)).toEqual(["c-1", "c-9"]);
      expect(d.mentionedNames).toEqual(["Marc"]);
      expect(d.description).toBe("DPA, SOC 2\n\nInternal: Sophie");
    }
  });

  it("another type: the names cited go to the description, no contact from a name", () => {
    const d = activityDefaultsFromNextStep(NS, { activityType: "TASK", citedContacts: CITED });
    expect(d.contacts.map((c) => c.id)).toEqual(["c-1"]); // the People's contact (2.2b)
    expect(d.mentionedNames).toEqual([]);
    expect(d.description).toBe(
      "DPA, SOC 2\n\nMentioned: Thomas Lefèvre, Laurent, Marc\n\nInternal: Sophie");
  });

  it("no topics, no names: an empty description", () => {
    const d = activityDefaultsFromNextStep({ ...NS, suggested_topics: "",
      suggested_people: [], suggested_people_names: [], suggested_internal_names: [] },
    { activityType: "TASK" });
    expect(d.description).toBe("");
  });

  it("without the server match yet: the 2.2b contacts only, nothing Mentioned", () => {
    const d = activityDefaultsFromNextStep(NS, { activityType: "MEETING" });
    expect(d.contacts.map((c) => c.id)).toEqual(["c-1"]);
    expect(d.mentionedNames).toEqual([]);
  });
});
