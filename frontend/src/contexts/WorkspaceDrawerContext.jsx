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
import { createContext, useContext, useState, useCallback, useMemo } from "react";

import { useMenuState } from "hooks/useMenuState";

// ==============================|| CONTEXT ||============================== //

const WorkspaceDrawerContext = createContext({
  isOpen: false,
  content: null,
  openDrawer: () => {},
  closeDrawer: () => {},
});

// ==============================|| PROVIDER ||============================== //

export function WorkspaceDrawerProvider({ children }) {
  const { handlerDrawerOpen } = useMenuState();

  // The injected content node is the single source of truth: a non-null node
  // means the drawer is open.
  const [content, setContent] = useState(null);
  const isOpen = content != null;

  const openDrawer = useCallback(
    (node) => {
      setContent(node ?? null);
      // Exclusivity: opening the workspace drawer collapses the left menu.
      handlerDrawerOpen(false);
    },
    [handlerDrawerOpen],
  );

  const closeDrawer = useCallback(() => setContent(null), []);

  const value = useMemo(
    () => ({ isOpen, content, openDrawer, closeDrawer }),
    [isOpen, content, openDrawer, closeDrawer],
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
