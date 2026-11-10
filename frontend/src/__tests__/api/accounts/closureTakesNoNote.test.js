// frontend/src/__tests__/api/accounts/closureTakesNoNote.test.js
//
// Sprint « Source / Notes » 1.5 — ONE note per activity, filled throughout its
// lifecycle, never at closure (PO). The front closure calls take no note any
// more (the backend dropped the parameter, 1.2): cancelActivity posts NO
// reason, recordCallNoAnswer posts NO outcome_notes — whatever the caller
// still passes.

import { describe, it, expect, vi, beforeEach } from "vitest";

const { post } = vi.hoisted(() => ({
  post: vi.fn(async () => ({ success: true, data: {} })),
}));
vi.mock("utils/axiosClient", () => ({ api: { post } }));
vi.mock("api/_swr", () => ({
  tenantKey: (k) => k,
  revalidateMultiple: vi.fn(),
  revalidateMetricSurfaces: vi.fn(),
  matchKey: vi.fn(),
}));

import { cancelActivity } from "api/accounts/activities";
import { recordCallNoAnswer } from "api/campaigns/campaigns";

const ACTIVITY_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479";

describe("closure calls take no note", () => {
  beforeEach(() => post.mockClear());

  it("cancelActivity posts no cancellation reason", async () => {
    await cancelActivity(ACTIVITY_ID, { notes: "A reason" });
    expect(post).toHaveBeenCalledTimes(1);
    const [url, body] = post.mock.calls[0];
    expect(url).toBe(`/module-activities/${ACTIVITY_ID}/cancel/`);
    expect(body ?? {}).toEqual({});
  });

  it("recordCallNoAnswer posts no outcome_notes", async () => {
    await recordCallNoAnswer(ACTIVITY_ID, "A note");
    expect(post).toHaveBeenCalledTimes(1);
    const [url, body] = post.mock.calls[0];
    expect(url).toBe(`/module-activities/${ACTIVITY_ID}/record-no-answer/`);
    expect(body ?? {}).toEqual({});
  });
});
