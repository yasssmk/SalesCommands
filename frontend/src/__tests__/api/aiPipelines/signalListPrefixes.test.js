// frontend/src/__tests__/api/aiPipelines/signalListPrefixes.test.js
//
// Sprint Next steps 5.10b (1) — the post-extraction revalidation list
// (SIGNAL_LIST_PREFIXES, api/aiPipelines/activityExtraction.js) is DERIVED from
// the signals endpoint map (api/signals/signals.js) + the aggregated endpoint
// (api/signals/aggregatedSignals.js) — one source, never hand-written: every
// prefix is a real route of the map, and no signal type's list is missing
// (before: "/module-signals/blocker/" singular — the route is blockers/ —
// and people / constraints / competitors absent).

import { describe, it, expect } from "vitest";

import { SIGNAL_LIST_PREFIXES } from "api/aiPipelines/activityExtraction";
import { SIGNAL_LIST_ENDPOINTS } from "api/signals/signals";
import { AGGREGATED_URL } from "api/signals/aggregatedSignals";

describe("SIGNAL_LIST_PREFIXES — derived from the endpoint map (5.10b)", () => {
  it("every prefix is a real route of the map (or the aggregated endpoint)", () => {
    const routes = new Set([...SIGNAL_LIST_ENDPOINTS, AGGREGATED_URL]);
    SIGNAL_LIST_PREFIXES.forEach((prefix) => expect(routes.has(prefix)).toBe(true));
  });

  it("no signal type's list is missing, nor the aggregated endpoint", () => {
    expect(new Set(SIGNAL_LIST_PREFIXES)).toEqual(new Set([AGGREGATED_URL, ...SIGNAL_LIST_ENDPOINTS]));
  });

  it("the map's list routes: the 9 signal types, plural where the API is", () => {
    expect(SIGNAL_LIST_ENDPOINTS).toEqual([
      "/module-signals/pain/",
      "/module-signals/objective/",
      "/module-signals/impact/",
      "/module-signals/tech-stack/",
      "/module-signals/blockers/",
      "/module-signals/next-steps/",
      "/module-signals/people/",
      "/module-signals/constraints/",
      "/module-signals/competitors/",
    ]);
  });
});
