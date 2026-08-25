// frontend/src/hooks/useSignalFilters.js
//
// Filter state for the flat "Signals" views, following the app's standard
// pending → Apply filter-panel pattern. Produces the aggregated-endpoint
// params (statuses, the selected signal_type subset, and the field-specific
// department / contact / scope filters).
//
//   filters          : applied filters driving the fetch
//   pending          : the drawer's working copy (Apply commits it)
//   updatePending    : (key, value) => void
//   apply / clear    : commit / reset
//   syncPending      : copy applied → pending (call when opening the drawer)
//   statuses         : ["PENDING","VALIDATED"] (+ "REJECTED" when opted in)
//   activeTypes      : selected type slugs ([] = all of the surface's types)
//   department       : StandardDepartment id ("" = none)
//   contactId        : selected contact's id (undefined = none)
//   scope            : "BUSINESS" | "DEPARTMENT" ("" = none)
//   activeCount      : number of active filters (for the toolbar badge)
//   hasPendingChanges: pending differs from applied (enables Apply)

import { useCallback, useMemo, useState } from "react";

const DEFAULT = {
  types: [],
  includeRejected: false,
  department: "",
  contact: null, // the whole contact object (AsyncContactSelect value)
  scope: "",
};

export default function useSignalFilters() {
  const [filters, setFilters] = useState(DEFAULT);
  const [pending, setPending] = useState(DEFAULT);

  const updatePending = useCallback((key, value) => {
    setPending((p) => ({ ...p, [key]: value }));
  }, []);

  const apply = useCallback(() => setFilters(pending), [pending]);

  const clear = useCallback(() => {
    setPending(DEFAULT);
    setFilters(DEFAULT);
  }, []);

  const syncPending = useCallback(() => setPending(filters), [filters]);

  const statuses = useMemo(
    () =>
      filters.includeRejected
        ? ["PENDING", "VALIDATED", "REJECTED"]
        : ["PENDING", "VALIDATED"],
    [filters.includeRejected],
  );

  const activeCount = useMemo(
    () =>
      filters.types.length +
      (filters.includeRejected ? 1 : 0) +
      (filters.department ? 1 : 0) +
      (filters.contact ? 1 : 0) +
      (filters.scope ? 1 : 0),
    [filters],
  );

  const hasPendingChanges = useMemo(
    () =>
      pending.includeRejected !== filters.includeRejected ||
      pending.department !== filters.department ||
      pending.scope !== filters.scope ||
      (pending.contact?.id ?? null) !== (filters.contact?.id ?? null) ||
      pending.types.length !== filters.types.length ||
      pending.types.some((t) => !filters.types.includes(t)),
    [pending, filters],
  );

  return {
    filters,
    pending,
    updatePending,
    apply,
    clear,
    syncPending,
    statuses,
    activeTypes: filters.types,
    department: filters.department || undefined,
    contactId: filters.contact?.id || undefined,
    scope: filters.scope || undefined,
    activeCount,
    hasPendingChanges,
  };
}
