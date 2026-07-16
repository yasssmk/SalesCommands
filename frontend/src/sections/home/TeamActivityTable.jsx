// frontend/src/sections/home/TeamActivityTable.jsx

'use client';

import PropTypes from 'prop-types';
import { useCallback, useEffect, useMemo, useState } from 'react';

import Typography from '@mui/material/Typography';

import useLocalStorage from 'hooks/useLocalStorage';
import { useGetTeamTodoActivities } from 'api/bi/todo';

import TodoActivityTable from './TodoActivityTable';

// ==============================|| TEAM ACTIVITY TABLE — the manager's team todo rows ||============================== //

// Column id -> backend ordering field. Person (owner) sorts by last name; Team
// has no backend ordering field so it stays non-sortable.
const COLUMN_TO_BACKEND_FIELD = {
  owner: 'owner__last_name',
  team: 'owner__team__name',
  title: 'title',
  activity_type: 'activity_type',
  account: 'account__company_name',
  context: 'context_kind',
  name: 'context_name',
  effective_date: 'effective_date',
};

function toOrdering(sorting) {
  if (!sorting || !sorting.length) return '';
  return sorting
    .map(({ id, desc }) => {
      const field = COLUMN_TO_BACKEND_FIELD[id] || id;
      return desc ? `-${field}` : field;
    })
    .join(',');
}

/**
 * The manager view's team todo rows, from /bi/todo/team/. Adds leading Person +
 * Team columns and owns page / page size / sorting / search; `team` and `owner`
 * come from the shared filter state (the standard filter panel + the bloc-1
 * drill-down). The advanced-filter panel/chips props are forwarded to the table.
 */
export default function TeamActivityTable({
  team,
  owner,
  advancedFilterPanel,
  advancedFilters,
  advancedFilterCount,
  onAdvancedFilterOpen,
  onAdvancedFilterRemove,
  onAdvancedFilterClear,
}) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage('teamActivityTablePageSize', 10);
  const [sorting, setSorting] = useState([]);
  const [search, setSearch] = useState('');
  const validPageSize = Number(pageSize) > 0 ? Number(pageSize) : 10;

  const ordering = useMemo(() => toOrdering(sorting), [sorting]);

  // A new team/person is a new list — back to page 1.
  useEffect(() => {
    setPage(1);
  }, [team, owner]);

  const { activities, activitiesCount, activitiesLoading, activitiesError, swrKey } =
    useGetTeamTodoActivities({ scope: 'team', team, owner, page, pageSize: validPageSize, search, ordering });

  const handlePaginationChange = useCallback(
    ({ page: newPage, pageSize: newSize }) => {
      setPage(newPage);
      const size = Number(newSize);
      if (!Number.isNaN(size) && size > 0 && size !== validPageSize) setPageSize(size);
    },
    [setPageSize, validPageSize],
  );

  const handleSortingChange = useCallback((updater) => {
    setSorting((prev) => (typeof updater === 'function' ? updater(prev) : updater));
    setPage(1);
  }, []);

  const handleSearchChange = useCallback((value) => {
    setSearch(value || '');
    setPage(1);
  }, []);

  const leadingColumns = useMemo(
    () => [
      {
        header: 'Person',
        id: 'owner', // -> owner__last_name (server ordering)
        // accessorFn REQUIRED for sortability: TanStack getCanSort() gates on
        // !!accessorFn, so a display column (id + cell) is never sortable. The
        // server orders by owner__last_name; mirror the person's name here so a
        // reader doesn't mistake it for client-side sorting (sorting stays
        // server-side via onSortingChange -> ordering).
        accessorFn: (row) => row.owner?.last_name || row.owner?.full_name || row.owner?.email || '',
        cell: ({ row }) => {
          const o = row.original.owner;
          return <Typography variant="body2">{o?.full_name || o?.email || '—'}</Typography>;
        },
      },
      {
        header: 'Team',
        id: 'team', // -> owner__team__name
        // accessorFn -> sortable (see Person). Mirror owner__team__name.
        accessorFn: (row) => row.team?.name || '',
        cell: ({ row }) => (
          <Typography variant="body2">{row.original.team?.name || '—'}</Typography>
        ),
      },
    ],
    [],
  );

  return (
    <TodoActivityTable
      activities={activities}
      activitiesCount={activitiesCount}
      activitiesLoading={activitiesLoading}
      activitiesError={activitiesError}
      swrKey={swrKey}
      page={page}
      onPaginationChange={handlePaginationChange}
      pageSize={validPageSize}
      sorting={sorting}
      onSortingChange={handleSortingChange}
      onSearchChange={handleSearchChange}
      leadingColumns={leadingColumns}
      emptyDescription="No open tasks for this selection."
      advancedFilterPanel={advancedFilterPanel}
      advancedFilters={advancedFilters}
      advancedFilterCount={advancedFilterCount}
      onAdvancedFilterOpen={onAdvancedFilterOpen}
      onAdvancedFilterRemove={onAdvancedFilterRemove}
      onAdvancedFilterClear={onAdvancedFilterClear}
    />
  );
}

TeamActivityTable.propTypes = {
  team: PropTypes.string,
  owner: PropTypes.string,
  advancedFilterPanel: PropTypes.node,
  advancedFilters: PropTypes.array,
  advancedFilterCount: PropTypes.number,
  onAdvancedFilterOpen: PropTypes.func,
  onAdvancedFilterRemove: PropTypes.func,
  onAdvancedFilterClear: PropTypes.func,
};

export { COLUMN_TO_BACKEND_FIELD };
