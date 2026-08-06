// frontend/src/__tests__/api/campaigns/enrollTargetChannelOverride.test.js
//
// enrollTarget must PROPAGATE an optional per-contact channel_override to the
// backend. The function destructures a fixed key set and rebuilds the POST body
// (the same shape that once dropped `strict`), so channel_override only reaches
// the backend if it is explicitly forwarded. When absent it must be omitted from
// the body (not sent as undefined), matching the other optional keys.

import { describe, it, expect, vi, beforeEach } from "vitest";

const post = vi.fn(() => Promise.resolve({ success: true, data: {} }));

vi.mock("utils/axiosClient", () => ({
  api: {
    post: (...a) => post(...a),
    delete: vi.fn(),
    get: vi.fn(),
  },
}));

vi.mock("api/_swr", () => ({
  revalidateMultiple: vi.fn(),
  tenantKey: (url) => url,
}));

import { enrollTarget } from "api/campaigns/campaigns";

const CID = "11111111-1111-4111-8111-111111111111";
const AID = "33333333-3333-4333-8333-333333333333";
const CCID = "22222222-2222-4222-8222-222222222222";

beforeEach(() => vi.clearAllMocks());

const lastBody = () => post.mock.calls.at(-1)[1];

describe("enrollTarget — channel_override propagation", () => {
  it("forwards channel_override='NO_CALLS' in the POST body when provided", async () => {
    await enrollTarget(CID, {
      account_id: AID,
      type: "CONTACT",
      contact_ids: [CCID],
      channel_override: "NO_CALLS",
    });

    expect(lastBody().channel_override).toBe("NO_CALLS");
  });

  it("omits channel_override from the body when not provided", async () => {
    await enrollTarget(CID, {
      account_id: AID,
      type: "CONTACT",
      contact_ids: [CCID],
    });

    expect("channel_override" in lastBody()).toBe(false);
  });
});
