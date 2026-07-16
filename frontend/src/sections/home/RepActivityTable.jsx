// frontend/src/sections/home/RepActivityTable.jsx

'use client';

import PropTypes from 'prop-types';
import { useCallback, useEffect, useMemo, useState } from 'react';

import useLocalStorage from 'hooks/useLocalStorage';
import { useGetTodoActivities } from 'api/bi/todo';

import TodoActivityTable from './TodoActivityTable';

// ==============================|| REP ACTIVITY TABLE — the rep's todo rows for a window ||============================== //

// Column id -> backend ordering field (the server whitelist). Only these columns
// are sortable; the rest set enableSorting:false in TodoActivityTable.
const COLUMN_TO_BACKEND_FIELD = {
  title: 'title',
  activity_type: 'activity_type',
  account: 'account__company_name',
  context: 'context_kind',
  name: 'context_name',
  effective_date: 'effective_date',
};

function toOrdering(sorting) {
  if (!sorting || !sorting.length) return ''; // empty -> backend default (effective_date asc)
  return sorting
    .map(({ id, desc }) => {
      const field = COLUMN_TO_BACKEND_FIELD[id] || id;
      return desc ? `-${field}` : field;
    })
    .join(',');
}

/**
 * The rep's todo rows for the active window. Owns page / persisted page size /
 * sorting / search and feeds the /bi/todo/ rows into the shared TodoActivityTable.
 * Sort + search are server-side. The page resets when the window changes.
 */
export default function RepActivityTable({ window, scope = 'mine' }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage('repActivityTablePageSize', 10);
  const [sorting, setSorting] = useState([]);
  const [search, setSearch] = useState('');
  const validPageSize = Number(pageSize) > 0 ? Number(pageSize) : 10;

  const ordering = useMemo(() => toOrdering(sorting), [sorting]);

  // A new window is a new list — go back to page 1.
  useEffect(() => {
    setPage(1);
  }, [window]);

  const { activities, activitiesCount, activitiesLoading, activitiesError, swrKey } =
    useGetTodoActivities({ scope, window, page, pageSize: validPageSize, search, ordering });

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
    />
  );
}

RepActivityTable.propTypes = {
  window: PropTypes.string,
  scope: PropTypes.string,
};

export { COLUMN_TO_BACKEND_FIELD };
