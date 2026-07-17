// frontend/src/__tests__/hooks/useTeamTodoFilters.test.js

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import useTeamTodoFilters from 'hooks/useTeamTodoFilters';

describe('useTeamTodoFilters', () => {
  it('starts empty: no apiFilters, zero active count', () => {
    const { result } = renderHook(() => useTeamTodoFilters());
    expect(result.current.apiFilters).toEqual({});
    expect(result.current.activeFiltersCount).toBe(0);
  });

  it('pending -> apply commits team/owner into apiFilters (empties dropped)', () => {
    const { result } = renderHook(() => useTeamTodoFilters());
    act(() => result.current.updatePendingFilter('team', 't1'));
    // Not applied yet.
    expect(result.current.apiFilters).toEqual({});
    act(() => result.current.applyFilters());
    expect(result.current.apiFilters).toEqual({ team: 't1' });
    expect(result.current.activeFiltersCount).toBe(1);
  });

  it('applyFilterImmediate sets applied AND pending in one step (the drill-down path)', () => {
    const { result } = renderHook(() => useTeamTodoFilters());
    act(() => result.current.applyFilterImmediate({ owner: 'u9' }));
    expect(result.current.apiFilters).toEqual({ owner: 'u9' });
    expect(result.current.pendingFilters.owner).toBe('u9'); // drawer stays in sync
  });

  it('clearFilters resets everything', () => {
    const { result } = renderHook(() => useTeamTodoFilters());
    act(() => result.current.applyFilterImmediate({ team: 't1', owner: 'u9' }));
    expect(result.current.activeFiltersCount).toBe(2);
    act(() => result.current.clearFilters());
    expect(result.current.apiFilters).toEqual({});
    expect(result.current.activeFiltersCount).toBe(0);
  });
});
