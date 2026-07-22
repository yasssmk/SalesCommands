// frontend/src/__tests__/api/campaigns/campaignSchedule.test.js
//
// Unit tests for getCampaignScheduleLine — the status→date rule shared by the
// campaign card and the workspace header. Reads the REAL planned_*/actual_*
// fields (never start_date/end_date), one field set per lifecycle status.

import { describe, it, expect } from "vitest";
import { getCampaignScheduleLine } from "api/campaigns/campaigns";

describe("getCampaignScheduleLine", () => {
  it("DRAFT → 'Starts {planned_start_date}'", () => {
    const r = getCampaignScheduleLine({
      status: "DRAFT",
      planned_start_date: "2026-08-01",
      planned_end_date: "2026-09-01",
    });
    expect(r).toEqual({ text: "Starts 2026-08-01", tone: "default" });
  });

  it("ACTIVE → actual_start_date → planned_end_date, default tone when end is future", () => {
    const r = getCampaignScheduleLine({
      status: "ACTIVE",
      actual_start_date: "2026-08-05",
      planned_start_date: "2026-08-01",
      planned_end_date: "2999-09-01",
    });
    expect(r.text).toBe("2026-08-05 → 2999-09-01");
    expect(r.tone).toBe("default");
  });

  it("ACTIVE with a passed planned end → warning tone", () => {
    const r = getCampaignScheduleLine({
      status: "ACTIVE",
      actual_start_date: "2020-01-01",
      planned_end_date: "2020-02-01",
    });
    expect(r.text).toBe("2020-01-01 → 2020-02-01");
    expect(r.tone).toBe("warning");
  });

  it("PAUSED falls back to planned_start when actual_start is absent", () => {
    const r = getCampaignScheduleLine({
      status: "PAUSED",
      planned_start_date: "2026-08-01",
      planned_end_date: "2999-09-01",
    });
    expect(r.text).toBe("2026-08-01 → 2999-09-01");
    expect(r.tone).toBe("default");
  });

  it("COMPLETED → 'Completed the {actual_end_date}'", () => {
    const r = getCampaignScheduleLine({
      status: "COMPLETED",
      actual_end_date: "2026-09-10",
    });
    expect(r).toEqual({ text: "Completed the 2026-09-10", tone: "default" });
  });

  it("CANCELLED → 'Cancelled', no date (no cancelled_at field)", () => {
    const r = getCampaignScheduleLine({
      status: "CANCELLED",
      planned_start_date: "2026-08-01",
      actual_end_date: "2026-09-10",
    });
    expect(r).toEqual({ text: "Cancelled", tone: "default" });
    expect(r.text).not.toMatch(/\d{4}-\d{2}-\d{2}/);
  });

  it("missing dates degrade to the em-dash fallback, never a crash", () => {
    const r = getCampaignScheduleLine({ status: "DRAFT" });
    expect(r.text).toBe("Starts —");
  });
});
