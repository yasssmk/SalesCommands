// frontend/src/__tests__/utils/workspaceTabs.test.js
//
// The workspace tab-value resolver. Guards the MUI Tabs `value` against stale
// `?tab=` ids left in bookmarks/history after a tab is removed — chiefly the
// "qualification" tab, whose view is now the Grouped mode of the Signals tab.

import { describe, it, expect } from "vitest";
import {
  resolveWorkspaceTab,
  LEGACY_TAB_REDIRECTS,
} from "utils/workspaceTabs";

const ACCOUNT_TAB_IDS = [
  "overview",
  "decision-cycle",
  "activities",
  "contacts",
  "signals",
];

describe("resolveWorkspaceTab", () => {
  it("routes the removed 'qualification' tab to 'signals' (its Grouped mode)", () => {
    expect(resolveWorkspaceTab("qualification", ACCOUNT_TAB_IDS, "overview")).toBe(
      "signals",
    );
  });

  it("passes a live tab id through unchanged", () => {
    expect(resolveWorkspaceTab("contacts", ACCOUNT_TAB_IDS, "overview")).toBe(
      "contacts",
    );
    expect(resolveWorkspaceTab("signals", ACCOUNT_TAB_IDS, "overview")).toBe(
      "signals",
    );
  });

  it("falls back to the default tab for a missing value", () => {
    expect(resolveWorkspaceTab(null, ACCOUNT_TAB_IDS, "overview")).toBe("overview");
    expect(resolveWorkspaceTab(undefined, ACCOUNT_TAB_IDS, "overview")).toBe(
      "overview",
    );
    expect(resolveWorkspaceTab("", ACCOUNT_TAB_IDS, "overview")).toBe("overview");
  });

  it("falls back to the default tab for an unknown value", () => {
    expect(resolveWorkspaceTab("bogus", ACCOUNT_TAB_IDS, "overview")).toBe(
      "overview",
    );
  });

  it("falls back to default when a redirect target is not a live tab in this workspace", () => {
    // A workspace that has no 'signals' tab can't honor the qualification→signals
    // redirect — it must not hand back an invalid id.
    expect(resolveWorkspaceTab("qualification", ["overview", "timeline"], "overview")).toBe(
      "overview",
    );
  });

  it("maps qualification → signals in the legacy redirect table", () => {
    expect(LEGACY_TAB_REDIRECTS.qualification).toBe("signals");
  });
});
