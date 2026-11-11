// frontend/src/__tests__/api/accounts/saveActivityNotes.test.js
//
// Sprint « Source / Notes » — notes panel, N2: the autosave's API.
//   - saveActivityNotes: POST /module-activities/{id}/notes/ { outcome_notes }
//     — NO cascade revalidation (it fires at every pause in typing);
//   - saveActivityNotesKeepalive: fetch keepalive + credentials "include"
//     (the HttpOnly cookie), against the API base URL.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const { post, revalidateMetricSurfaces, revalidateMultiple } = vi.hoisted(() => ({
  post: vi.fn(),
  revalidateMetricSurfaces: vi.fn(),
  revalidateMultiple: vi.fn(),
}));
vi.mock("utils/axiosClient", () => ({ api: { post } }));
vi.mock("api/_swr", () => ({
  tenantKey: (k) => k,
  revalidateMultiple,
  revalidateMetricSurfaces,
  matchKey: vi.fn(),
}));
vi.mock("../../../config/auth", () => ({
  authConfig: { API_BASE_URL: "https://api.example.test" },
}));

import {
  saveActivityNotes,
  saveActivityNotesKeepalive,
} from "api/accounts/activities";

const ACTIVITY_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479";

describe("saveActivityNotes", () => {
  beforeEach(() => vi.clearAllMocks());

  it("posts the whole note to the notes endpoint", async () => {
    post.mockResolvedValue({
      success: true,
      data: { success: true, data: { outcome_notes: "N", updated_at: "2026-11-11T10:00:00Z" } },
    });
    const result = await saveActivityNotes(ACTIVITY_ID, "N");
    expect(post).toHaveBeenCalledTimes(1);
    const [url, body] = post.mock.calls[0];
    expect(url).toBe(`/module-activities/${ACTIVITY_ID}/notes/`);
    expect(body).toEqual({ outcome_notes: "N" });
    expect(result).toEqual({
      success: true,
      data: { outcome_notes: "N", updated_at: "2026-11-11T10:00:00Z" },
    });
  });

  it("revalidates nothing (no cascade at every pause in typing)", async () => {
    post.mockResolvedValue({ success: true, data: { data: {} } });
    await saveActivityNotes(ACTIVITY_ID, "N");
    expect(revalidateMetricSurfaces).not.toHaveBeenCalled();
    expect(revalidateMultiple).not.toHaveBeenCalled();
  });

  it("returns the server's error as is", async () => {
    post.mockResolvedValue({ success: false, error: "Locked", status: 400 });
    const result = await saveActivityNotes(ACTIVITY_ID, "N");
    expect(result).toMatchObject({ success: false, error: "Locked", status: 400 });
  });

  it("refuses an invalid id without a request", async () => {
    const result = await saveActivityNotes("nope", "N");
    expect(result).toMatchObject({ success: false, status: 400 });
    expect(post).not.toHaveBeenCalled();
  });
});

describe("saveActivityNotesKeepalive", () => {
  let fetchSpy;
  beforeEach(() => {
    fetchSpy = vi.fn(() => Promise.resolve({ ok: true }));
    vi.stubGlobal("fetch", fetchSpy);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("sends a keepalive fetch with the cookie (credentials include)", () => {
    expect(saveActivityNotesKeepalive(ACTIVITY_ID, "Last words")).toBe(true);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe(`https://api.example.test/module-activities/${ACTIVITY_ID}/notes/`);
    expect(init).toMatchObject({
      method: "POST",
      keepalive: true,
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    expect(JSON.parse(init.body)).toEqual({ outcome_notes: "Last words" });
  });

  it("never throws (fire-and-forget)", () => {
    fetchSpy.mockImplementation(() => {
      throw new Error("boom");
    });
    expect(saveActivityNotesKeepalive(ACTIVITY_ID, "x")).toBe(false);
    fetchSpy.mockImplementation(() => Promise.reject(new Error("offline")));
    expect(saveActivityNotesKeepalive(ACTIVITY_ID, "x")).toBe(true);
  });

  it("sends nothing for an invalid id", () => {
    expect(saveActivityNotesKeepalive("nope", "x")).toBe(false);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
