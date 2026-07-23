// frontend/src/__tests__/api/campaigns/playlistRevalidation.test.js
//
// Every target-status-changing action routes its cache invalidation through the
// shared revalidateCampaignPlaylist helper, so the completed accordion (and the
// rest of the playlist) refresh after a stop / enroll / remove / complete —
// not just the Targets table.
//
// The helper uses the SHORT /module-activities/?campaign={id} prefix because
// revalidateMultiple matches by startsWith: a key pinned to page_size=200 does
// NOT prefix the hook's page_size=25 keys, which is the bug that left the
// accordion stale. Both facts are pinned below.

import { describe, it, expect, vi, beforeEach } from "vitest";

const post = vi.fn(() => Promise.resolve({ success: true, data: {} }));
const del = vi.fn(() => Promise.resolve({ success: true }));

vi.mock("utils/axiosClient", () => ({
  api: {
    post: (...a) => post(...a),
    delete: (...a) => del(...a),
    get: vi.fn(),
  },
}));

vi.mock("api/_swr", () => ({
  revalidateMultiple: vi.fn(),
  tenantKey: (url) => url,
}));

import {
  stopTarget,
  pauseTarget,
  resumeTarget,
  removeTargets,
  enrollTarget,
  completePlaylistActivity,
} from "api/campaigns/campaigns";
import { revalidateMultiple } from "api/_swr";

const CID = "11111111-1111-4111-8111-111111111111"; // campaign id
const CCID = "22222222-2222-4222-8222-222222222222"; // campaign-contact id
const AID = "33333333-3333-4333-8333-333333333333"; // account id
const ACTID = "44444444-4444-4444-8444-444444444444"; // activity id

beforeEach(() => vi.clearAllMocks());

const lastPrefixes = () => revalidateMultiple.mock.calls.at(-1)[0];

const cases = [
  ["stopTarget", () => stopTarget(CCID, CID)],
  ["pauseTarget", () => pauseTarget(CCID, CID)],
  ["resumeTarget", () => resumeTarget(CCID, CID)],
  ["removeTargets", () => removeTargets(CID, [CCID])],
  [
    "enrollTarget",
    () => enrollTarget(CID, { account_id: AID, type: "CONTACT", contact_ids: [CCID] }),
  ],
  [
    "completePlaylistActivity",
    () => completePlaylistActivity(ACTID, CID, { outcome: "NO_ANSWER" }),
  ],
];

describe("campaign playlist revalidation — shared helper", () => {
  it.each(cases)(
    "%s revalidates the accordion + playlist + targets prefixes with the campaignId",
    async (_name, fn) => {
      await fn();

      expect(revalidateMultiple).toHaveBeenCalledTimes(1);
      const prefixes = lastPrefixes();

      // The completed-accordion prefix (the fix) …
      expect(prefixes).toContain(`/module-activities/?campaign=${CID}`);
      // … the to-do playlist …
      expect(prefixes).toContain(`/campaigns/${CID}/playlist/`);
      // … and the Targets table (union coverage — no key lost).
      expect(prefixes).toContain(`/campaigns/contacts/?campaign=${CID}`);
    },
  );

  it("the short accordion prefix matches a real accordion key; the old page_size=200 key did not", () => {
    const accordionKey =
      `/module-activities/?campaign=${CID}&status=COMPLETED&active_sequence=true` +
      `&ordering=-completed_at&page_size=25&page=1`;

    // The fix: the short prefix is a genuine prefix of the hook key.
    expect(accordionKey.startsWith(`/module-activities/?campaign=${CID}`)).toBe(true);

    // The bug: the previous page_size=200 key is NOT a prefix of the page_size=25
    // hook key, so revalidateMultiple never matched the accordion.
    const oldPinnedKey =
      `/module-activities/?campaign=${CID}&status=COMPLETED&active_sequence=true&page_size=200`;
    expect(accordionKey.startsWith(oldPinnedKey)).toBe(false);
  });
});
