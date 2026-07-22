// frontend/src/__tests__/hooks/listFiltersOwnerScope.test.jsx
//
// The Territory and Campaign list filter hooks seed owner_scope from the user's
// tier (individual → mine, manager → team, admin → all), re-apply the default on
// every mount (no persistence), and clear back to the tier default (not 'all').
//
// Mirrors useTeamTodoFilters.test.js (renderHook + act) with the roleAware
// per-test useAuth override (mock the hook as a vi.fn(), set the tier per test).

import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useAuth } from "hooks/useAuth";
import useTerritoryListFilters from "hooks/useTerritoryListFilters";
import useCampaignListFilters from "hooks/useCampaignListFilters";

// Replace the global useAuth mock with a spy so each test picks the tier.
vi.mock("hooks/useAuth", () => ({ useAuth: vi.fn() }));

// Real /me (UserSerializer) shape: `role` is a bare UUID string, tier is the
// top-level `role_tier`, is_manager/is_superuser are flat booleans.
const asTier = (role_tier) =>
  vi.mocked(useAuth).mockReturnValue({
    user: {
      id: "u1",
      role: "5f3e9c00-0000-0000-0000-000000000001",
      role_tier,
      is_manager: role_tier === "manager",
      is_superuser: false,
    },
    isAuthenticated: true,
  });

const HOOKS = [
  ["useTerritoryListFilters", useTerritoryListFilters],
  ["useCampaignListFilters", useCampaignListFilters],
];

describe.each(HOOKS)("%s — tier-based owner_scope seed", (_name, useHook) => {
  it("individual → mine on both filters and pendingFilters (chip active)", () => {
    asTier("individual");
    const { result } = renderHook(() => useHook());
    expect(result.current.filters.owner_scope).toBe("mine");
    expect(result.current.pendingFilters.owner_scope).toBe("mine");
    expect(result.current.apiFilters.owner_scope).toBe("mine");
    expect(result.current.activeFiltersCount).toBe(1);
  });

  it("manager → team", () => {
    asTier("manager");
    const { result } = renderHook(() => useHook());
    expect(result.current.filters.owner_scope).toBe("team");
    expect(result.current.pendingFilters.owner_scope).toBe("team");
    expect(result.current.apiFilters.owner_scope).toBe("team");
  });

  it("admin → all (no chip: owner_scope omitted from apiFilters, count 0)", () => {
    asTier("admin");
    const { result } = renderHook(() => useHook());
    expect(result.current.filters.owner_scope).toBe("all");
    expect(result.current.apiFilters.owner_scope).toBeUndefined();
    expect(result.current.activeFiltersCount).toBe(0);
  });

  it("re-mount re-applies the default (a widened choice is not persisted)", () => {
    asTier("manager");
    const first = renderHook(() => useHook());
    expect(first.result.current.filters.owner_scope).toBe("team");
    // Widen to all via the chip-removal path.
    act(() => first.result.current.removeFilter("owner_scope", "all"));
    expect(first.result.current.filters.owner_scope).toBe("all");
    first.unmount();
    // Fresh visit → tier default re-applied, nothing carried over.
    const second = renderHook(() => useHook());
    expect(second.result.current.filters.owner_scope).toBe("team");
  });

  it("clearFilters resets to the tier default, not 'all'", () => {
    asTier("manager");
    const { result } = renderHook(() => useHook());
    act(() => result.current.removeFilter("owner_scope", "all"));
    expect(result.current.filters.owner_scope).toBe("all");
    act(() => result.current.clearFilters());
    expect(result.current.filters.owner_scope).toBe("team");
    expect(result.current.pendingFilters.owner_scope).toBe("team");
  });
});
