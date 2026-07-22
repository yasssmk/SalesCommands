// frontend/src/__tests__/hooks/dcFiltersOwnerScope.test.jsx
//
// useDecisionCycleFilters seeds owner_scope from the user's tier (individual →
// mine, manager → team, admin → all), re-applies the default on every mount (no
// persistence), and clears back to the tier default (not 'all') — same as the
// Territory/Campaign list hooks. Mirrors listFiltersOwnerScope.test.jsx, with a
// DC-specific case for the initialFilters override the DC hook accepts.

import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useAuth } from "hooks/useAuth";
import useDecisionCycleFilters from "hooks/useDecisionCycleFilters";

// Replace the global useAuth mock with a spy so each test picks the tier. Real
// /me shape: role is a name string, the tier is the top-level role_tier.
vi.mock("hooks/useAuth", () => ({ useAuth: vi.fn() }));

const asTier = (role_tier) =>
  vi.mocked(useAuth).mockReturnValue({
    user: {
      id: "u1",
      role: "Sales Rep",
      role_tier,
      is_manager: role_tier === "manager",
      is_superuser: false,
    },
    isAuthenticated: true,
  });

describe("useDecisionCycleFilters — tier-based owner_scope seed", () => {
  it("individual → mine on both filters and pendingFilters (chip active)", () => {
    asTier("individual");
    const { result } = renderHook(() => useDecisionCycleFilters());
    expect(result.current.filters.owner_scope).toBe("mine");
    expect(result.current.pendingFilters.owner_scope).toBe("mine");
    expect(result.current.apiFilters.owner_scope).toBe("mine");
    expect(result.current.activeFiltersCount).toBe(1);
  });

  it("manager → team", () => {
    asTier("manager");
    const { result } = renderHook(() => useDecisionCycleFilters());
    expect(result.current.filters.owner_scope).toBe("team");
    expect(result.current.pendingFilters.owner_scope).toBe("team");
    expect(result.current.apiFilters.owner_scope).toBe("team");
  });

  it("admin → all (no chip: owner_scope omitted from apiFilters, count 0)", () => {
    asTier("admin");
    const { result } = renderHook(() => useDecisionCycleFilters());
    expect(result.current.filters.owner_scope).toBe("all");
    expect(result.current.apiFilters.owner_scope).toBeUndefined();
    expect(result.current.activeFiltersCount).toBe(0);
  });

  it("re-mount re-applies the default (a widened choice is not persisted)", () => {
    asTier("manager");
    const first = renderHook(() => useDecisionCycleFilters());
    expect(first.result.current.filters.owner_scope).toBe("team");
    // Widen to all via the drawer apply path (this hook has no removeFilter).
    act(() => first.result.current.updatePendingFilter("owner_scope", "all"));
    act(() => first.result.current.applyFilters());
    expect(first.result.current.filters.owner_scope).toBe("all");
    first.unmount();
    // Fresh visit → tier default re-applied, nothing carried over.
    const second = renderHook(() => useDecisionCycleFilters());
    expect(second.result.current.filters.owner_scope).toBe("team");
  });

  it("clearFilters resets to the tier default, not 'all'", () => {
    asTier("manager");
    const { result } = renderHook(() => useDecisionCycleFilters());
    act(() => result.current.updatePendingFilter("owner_scope", "all"));
    act(() => result.current.applyFilters());
    expect(result.current.filters.owner_scope).toBe("all");
    act(() => result.current.clearFilters());
    expect(result.current.filters.owner_scope).toBe("team");
    expect(result.current.pendingFilters.owner_scope).toBe("team");
  });

  it("an explicit initialFilters.owner_scope still overrides the tier seed", () => {
    asTier("individual");
    const { result } = renderHook(() =>
      useDecisionCycleFilters({ owner_scope: "team" }),
    );
    expect(result.current.filters.owner_scope).toBe("team");
    expect(result.current.pendingFilters.owner_scope).toBe("team");
  });
});
