// frontend/src/contexts/BreadcrumbContext.jsx
//
// UX Activity L0 — STATE ONLY for the contextual breadcrumb.
//
// The audit proved there is no mechanism for a page to feed a contextual trail
// ("Account › DC › Activity") to the layout: the only layout breadcrumb is the
// legacy @extended/Breadcrumbs, derived from the MENU (title/href of nav items),
// which cannot carry data-driven page context. This provider is that missing
// channel: a page pushes its trail via setCrumbs(items); the layout bar
// (components/BreadcrumbBar) reads it. It renders NO DOM of its own.
//
// FORM cloned from contexts/WorkspaceDrawerContext.jsx (B3.5.0): createContext
// with a no-op default, a Provider holding state + a stable setter (useCallback
// so a page's useEffect push never loops), a useX() hook, and a memoized value.
//
// Each item = { label, href? }. `href` optional: when present (and not the last
// segment) the bar renders it as a clickable link; the last segment is the
// current page.

"use client";

import PropTypes from "prop-types";
import { createContext, useContext, useState, useCallback, useMemo } from "react";

// ==============================|| CONTEXT ||============================== //

const BreadcrumbContext = createContext({
  crumbs: [],
  setCrumbs: () => {},
});

// ==============================|| PROVIDER ||============================== //

export function BreadcrumbProvider({ children }) {
  const [crumbs, setCrumbsState] = useState([]);

  // Stable setter: a page pushes its trail from a useEffect, so the identity
  // must not change between renders or the effect would loop.
  const setCrumbs = useCallback((items) => {
    setCrumbsState(Array.isArray(items) ? items : []);
  }, []);

  const value = useMemo(() => ({ crumbs, setCrumbs }), [crumbs, setCrumbs]);

  return (
    <BreadcrumbContext.Provider value={value}>
      {children}
    </BreadcrumbContext.Provider>
  );
}

BreadcrumbProvider.propTypes = {
  children: PropTypes.node,
};

// ==============================|| HOOK ||============================== //

export function useBreadcrumb() {
  return useContext(BreadcrumbContext);
}

export { BreadcrumbContext };
