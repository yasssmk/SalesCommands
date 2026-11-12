// frontend/src/components/drawer/UnsavedLinkGuard.jsx
//
// Sprint « Source / Notes » 2.3 — the INTERNAL LINKS guard. Next's App Router
// offers no way to block a navigation, and the coque's route-change effect
// (contexts/WorkspaceDrawerContext) runs AFTER it. So, while a source is
// MODIFIED (a drawer content OR a page field — hooks/useUnsavedChanges), a
// click on an internal link (breadcrumb, menu, page link) is intercepted in
// the CAPTURE phase on the document — before Next's <Link> handler — and the
// shared ConfirmDialog asks (the coque's guardUnsaved, same labels as 2.2):
// « Keep editing » → no navigation; « Discard » → router.push(link).
//
// NOT intercepted (the native / Next behaviour is kept):
//   - nothing modified;
//   - a new tab / window: ctrl / cmd / shift / alt, a non-primary button,
//     a target other than _self, a download link;
//   - an external link (another origin);
//   - a link without a route change (same path and query — e.g. a hash).
//
// NOT COVERED — the browser Back / Forward buttons: a popstate cannot be
// cancelled, the navigation has happened when it fires. beforeunload (2.2)
// covers the reload / tab close only.
//
// Mounted ONCE, beside the coque (layout/DashboardLayout), not link by link.
// Renders nothing; the confirmation is rendered by the coque (WorkspaceDrawer).

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";

// The internal destination of a click on a link, or null when it must not be
// intercepted (see the module docstring).
export function internalDestination(event) {
  if (event.defaultPrevented) return null;
  if (event.button !== 0) return null;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return null;
  const anchor = event.target?.closest?.("a[href]");
  if (!anchor) return null;
  const target = anchor.getAttribute("target");
  if (target && target !== "_self") return null;
  if (anchor.hasAttribute("download")) return null;

  const url = new URL(anchor.href, window.location.href);
  if (url.origin !== window.location.origin) return null;
  if (url.pathname === window.location.pathname && url.search === window.location.search) {
    return null;
  }
  return `${url.pathname}${url.search}${url.hash}`;
}

export default function UnsavedLinkGuard() {
  const router = useRouter();
  const { hasUnsaved, guardUnsaved } = useWorkspaceDrawer();

  useEffect(() => {
    const onClick = (event) => {
      if (!hasUnsaved()) return;
      const destination = internalDestination(event);
      if (!destination) return;
      // Stop the native navigation AND Next's <Link> handler (the capture
      // phase on the document runs before React's root listener).
      event.preventDefault();
      event.stopPropagation();
      guardUnsaved(() => router.push(destination));
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [hasUnsaved, guardUnsaved, router]);

  return null;
}
