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

import { useMenuState } from "hooks/useMenuState";

// ==============================|| CONTEXT ||============================== //

const WorkspaceDrawerContext = createContext({
  isOpen: false,
  content: null,
  title: null,
  openDrawer: () => {},
  closeDrawer: () => {},
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
  const isOpen = content != null;

  const openDrawer = useCallback(
    (node, options = {}) => {
      setContent(node ?? null);
      setTitle(options?.title ?? null);
      // Exclusivity: opening the workspace drawer collapses the left menu.
      handlerDrawerOpen(false);
    },
    [handlerDrawerOpen],
  );

  const closeDrawer = useCallback(() => {
    setContent(null);
    setTitle(null);
  }, []);

  // Reverse exclusivity: the hamburger lives in the shell (outside this
  // provider), so we OBSERVE the menu singleton instead of wiring the toggle.
  // Close the drawer only on a menu OPEN transition (false → true) — never on
  // its close, so openDrawer()'s own handlerDrawerOpen(false) can't loop.
  const prevMenuOpen = useRef(menuOpen);
  useEffect(() => {
    if (menuOpen && !prevMenuOpen.current) {
      setContent(null);
      setTitle(null);
    }
    prevMenuOpen.current = menuOpen;
  }, [menuOpen]);

  const value = useMemo(
    () => ({ isOpen, content, title, openDrawer, closeDrawer }),
    [isOpen, content, title, openDrawer, closeDrawer],
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
