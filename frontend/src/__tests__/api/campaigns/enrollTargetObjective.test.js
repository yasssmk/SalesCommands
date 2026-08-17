// frontend/src/__tests__/api/campaigns/enrollTargetObjective.test.js
//
// S13 sub-step 6c — enrollTarget() whitelists its POST-body keys; `objective`
// must be forwarded or it is silently dropped. This guards that gotcha.

import { describe, it, expect, vi, beforeEach } from "vitest";

const { post } = vi.hoisted(() => ({
  post: vi.fn(async () => ({ success: true, data: {} })),
}));
vi.mock("utils/axiosClient", () => ({ api: { post } }));
vi.mock("api/_swr", () => ({ tenantKey: (k) => k, revalidateMultiple: vi.fn() }));

import { enrollTarget } from "api/campaigns/campaigns";

const CAMPAIGN_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479";

describe("enrollTarget — objective forwarding", () => {
  beforeEach(() => post.mockClear());

  it("forwards `objective` in the POST body", async () => {
    await enrollTarget(CAMPAIGN_ID, {
      account_id: "acc1",
      contact_ids: ["c1"],
      type: "CONTACT",
      objective: "Chase the signed quote",
    });

    expect(post).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        type: "CONTACT",
        objective: "Chase the signed quote",
      }),
    );
  });

  it("defaults type to CONTACT (not the removed ACCOUNT)", async () => {
    await enrollTarget(CAMPAIGN_ID, { account_id: "acc1", contact_ids: ["c1"] });

    const body = post.mock.calls[0][1];
    expect(body.type).toBe("CONTACT");
  });

  it("omits objective when not provided", async () => {
    await enrollTarget(CAMPAIGN_ID, {
      account_id: "acc1",
      contact_ids: ["c1"],
      type: "CONTACT",
    });

    const body = post.mock.calls[0][1];
    expect(body.objective).toBeUndefined();
  });
});
