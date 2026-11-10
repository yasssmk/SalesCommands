// frontend/src/contexts/WorkspaceDrawerContext.jsx
//
// B3.5.0 — STATE ONLY for the single workspace drawer coque.
//
// One drawer coque per workspace; only the CONTENT changes (signal edit /
// signal detail / contact / notes). This provider holds that content and the
// open state. It renders NO DOM of its own — the visual coque is B3.5.1.
//
// Exclusivity with the global left menu: opening the workspace drawer collapses
// the menu via the existing useMenuState().handlerDrawerOpen(false)
// (hooks/useMenuState.js — the SWR singleton that also backs the sidebar). The
// reverse wiring (menu toggle → closeDrawer) is done at the hamburger in B3.5.2.
//
// « Source / Notes » 2.2 — the UNSAVED CHANGES guard, at this central point:
// a content (or a page field) declares itself MODIFIED through
// hooks/useUnsavedChanges (the drawer contents through DrawerContentLayout's
// `dirty`). While a DRAWER source is modified, replacing the content
// (openDrawer), closing it (closeDrawer, the coque's ×) or opening the menu
// asks first (`pendingDiscard`, rendered by the visual coque with the shared
// ConfirmDialog): « Keep editing » keeps the content, « Discard » applies the
// action. While ANY source is modified (drawer or page), beforeunload is
// prevented (reload / tab close). A route change cannot be blocked here (the
// pathname effect runs after the navigation): see 2.3.

"use client";

import PropTypes from "prop-types";
import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  useEffect,
  useRef,
} from "react";

import { usePathname } from "next/navigation";

import { useMenuState } from "hooks/useMenuState";
import { UNSAVED_SCOPE } from "utils/unsavedChanges";

// ==============================|| CONTEXT ||============================== //

const WorkspaceDrawerContext = createContext({
  isOpen: false,
  content: null,
  title: null,
  status: null,
  statusMap: null,
  hideClose: false,
  openDrawer: () => {},
  closeDrawer: () => {},
  registerUnsaved: () => {},
  releaseUnsaved: () => {},
  hasUnsaved: () => false,
  pendingDiscard: null,
  confirmDiscard: () => {},
  cancelDiscard: () => {},
});

// ==============================|| PROVIDER ||============================== //

export function WorkspaceDrawerProvider({ children }) {
  const { menuMaster, handlerDrawerOpen } = useMenuState();
  const menuOpen = Boolean(menuMaster?.isDashboardDrawerOpened);

  // The injected content node is the single source of truth: a non-null node
  // means the drawer is open.
  const [content, setContent] = useState(null);
  // Optional coque title (Option A): the coque renders it in its header, on the
  // close cross's line. Absent → the coque header shows the cross alone.
  const [title, setTitle] = useState(null);
  // Optional coque status pill (read drawers): `status` key resolved against
  // `statusMap` by the shared StatusPill (UI-1). Absent → no pill.
  const [status, setStatus] = useState(null);
  const [statusMap, setStatusMap] = useState(null);
  // Optional: when true the coque suppresses its own close cross (the injected
  // content renders its own — e.g. the Objective detail's in-header ×).
  const [hideClose, setHideClose] = useState(false);
  const isOpen = content != null;

  // ---- Unsaved changes registry (2.2) — id → scope. A ref: the guard reads
  //      it at the moment of the action; sources register synchronously at
  //      commit (useUnsavedChanges uses a layout effect).
  const unsavedRef = useRef(new Map());
  const registerUnsaved = useCallback((id, scope) => {
    unsavedRef.current.set(id, scope);
  }, []);
  const releaseUnsaved = useCallback((id) => {
    unsavedRef.current.delete(id);
  }, []);
  const hasUnsaved = useCallback(
    (scope) => [...unsavedRef.current.values()].some((s) => !scope || s === scope),
    [],
  );

  // The action waiting for « Discard » (null = no confirmation shown):
  // { apply, keep } — `keep` runs on « Keep editing » (e.g. re-fold the menu).
  const [pendingDiscard, setPendingDiscard] = useState(null);
  const guard = useCallback(
    (apply, keep) => {
      if (hasUnsaved(UNSAVED_SCOPE.DRAWER)) {
        setPendingDiscard({ apply, keep: keep ?? null });
        return;
      }
      apply();
    },
    [hasUnsaved],
  );

  const resetContent = useCallback(() => {
    setContent(null);
    setTitle(null);
    setStatus(null);
    setStatusMap(null);
    setHideClose(false);
  }, []);

  const openDrawer = useCallback(
    (node, options = {}) => {
      guard(() => {
        setContent(node ?? null);
        setTitle(options?.title ?? null);
        setStatus(options?.status ?? null);
        setStatusMap(options?.statusMap ?? null);
        setHideClose(Boolean(options?.hideClose));
        // Exclusivity: opening the workspace drawer collapses the left menu.
        handlerDrawerOpen(false);
      });
    },
    [guard, handlerDrawerOpen],
  );

  const closeDrawer = useCallback(() => {
    guard(resetContent);
  }, [guard, resetContent]);

  const confirmDiscard = useCallback(() => {
    const pending = pendingDiscard;
    setPendingDiscard(null);
    // The discarded content's sources go with it (it unmounts) — clear the
    // drawer scope now so the applied action is not intercepted again.
    for (const [id, scope] of unsavedRef.current) {
      if (scope === UNSAVED_SCOPE.DRAWER) unsavedRef.current.delete(id);
    }
    pending?.apply();
  }, [pendingDiscard]);

  const cancelDiscard = useCallback(() => {
    const pending = pendingDiscard;
    setPendingDiscard(null);
    pending?.keep?.();
  }, [pendingDiscard]);

  // beforeunload (reload / tab close) while ANY source is modified.
  useEffect(() => {
    const onBeforeUnload = (event) => {
      if (!hasUnsaved()) return;
      event.preventDefault();
      // Legacy browsers need a returnValue to show their native prompt.
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [hasUnsaved]);

  // Close the drawer on route change: navigating away from the workspace must
  // not leave a stale drawer open. Observe the Next pathname and close only on
  // an actual change (never on the first render, so opening the drawer on the
  // current page is untouched).
  const pathname = usePathname();
  const prevPathname = useRef(pathname);
  useEffect(() => {
    if (prevPathname.current !== pathname) {
      prevPathname.current = pathname;
      // The navigation already happened (it cannot be blocked here — 2.3
      // intercepts the internal links before it): close without asking.
      resetContent();
    }
  }, [pathname, resetContent]);

  // Reverse exclusivity: the hamburger lives in the shell (outside this
  // provider), so we OBSERVE the menu singleton instead of wiring the toggle.
  // Close the drawer only on a menu OPEN transition (false → true) — never on
  // its close, so openDrawer()'s own handlerDrawerOpen(false) can't loop.
  // 2.2: over a MODIFIED drawer, the menu opening asks first — « Keep
  // editing » re-folds the menu, « Discard » closes the drawer.
  const prevMenuOpen = useRef(menuOpen);
  useEffect(() => {
    if (menuOpen && !prevMenuOpen.current && isOpen) {
      guard(resetContent, () => handlerDrawerOpen(false));
    }
    prevMenuOpen.current = menuOpen;
  }, [menuOpen, isOpen, guard, resetContent, handlerDrawerOpen]);

  const value = useMemo(
    () => ({
      isOpen, content, title, status, statusMap, hideClose, openDrawer, closeDrawer,
      registerUnsaved, releaseUnsaved, hasUnsaved, pendingDiscard, confirmDiscard, cancelDiscard,
    }),
    [
      isOpen, content, title, status, statusMap, hideClose, openDrawer, closeDrawer,
      registerUnsaved, releaseUnsaved, hasUnsaved, pendingDiscard, confirmDiscard, cancelDiscard,
    ],
  );

  return (
    <WorkspaceDrawerContext.Provider value={value}>
      {children}
    </WorkspaceDrawerContext.Provider>
  );
}

WorkspaceDrawerProvider.propTypes = {
  children: PropTypes.node,
};

// ==============================|| HOOK ||============================== //

export function useWorkspaceDrawer() {
  return useContext(WorkspaceDrawerContext);
}

export { WorkspaceDrawerContext };
