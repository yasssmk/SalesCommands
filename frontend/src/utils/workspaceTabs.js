// frontend/src/utils/workspaceTabs.js
//
// Workspace tab-value resolution.
//
// Tab ids live in the URL (`?tab=`). When a tab is removed, URLs that still
// carry its id survive in bookmarks and browser history. Feeding that stale id
// straight to the MUI Tabs component logs:
//   "MUI: The `value` provided to the Tabs component is invalid."
// and leaves the tab strip with nothing selected.
//
// resolveWorkspaceTab() maps a removed tab id to where its content now lives,
// then validates the result against the workspace's live tab ids — falling back
// to the default tab for anything still unknown. So a legacy id always resolves
// to a real, selectable tab.

// Tabs removed during the Signals consolidation, mapped to their new home.
// The "qualification" tab is gone — its view is the Grouped mode of the Signals
// tab, so a legacy `?tab=qualification` link now lands on Signals.
export const LEGACY_TAB_REDIRECTS = Object.freeze({
  qualification: "signals",
});

/**
 * Resolve a raw `?tab=` value to a valid, selectable tab id.
 *
 * @param {string|null|undefined} rawTab - The tab id from the URL.
 * @param {string[]} validTabIds - The workspace's live tab ids.
 * @param {string} defaultTab - Fallback when the value is missing/unknown.
 * @returns {string} A tab id guaranteed to be in validTabIds (assuming
 *   defaultTab itself is valid).
 */
export function resolveWorkspaceTab(rawTab, validTabIds, defaultTab) {
  if (!rawTab) return defaultTab;
  const redirected = LEGACY_TAB_REDIRECTS[rawTab] ?? rawTab;
  return validTabIds.includes(redirected) ? redirected : defaultTab;
}
