// frontend/src/views/home/components/RepActivityTable.jsx

'use client';

import PropTypes from 'prop-types';
import { useCallback, useEffect, useState } from 'react';

import useLocalStorage from 'hooks/useLocalStorage';
import { useGetTodoActivities } from 'api/bi/todo';

import TodoActivityTable from './TodoActivityTable';

// ==============================|| REP ACTIVITY TABLE — the rep's todo rows for a window ||============================== //

/**
 * The rep's todo rows for the active window. A thin wrapper over the shared
 * TodoActivityTable: it owns the page state + persisted page size and feeds the
 * /bi/todo/ rows in. The page resets when the window filter changes.
 */
export default function RepActivityTable({ window, scope = 'mine' }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage('repActivityTablePageSize', 10);
  const validPageSize = Number(pageSize) > 0 ? Number(pageSize) : 10;

  // A new window is a new list — go back to page 1 (avoids requesting an
  // out-of-range page from the previous window).
  useEffect(() => {
    setPage(1);
  }, [window]);

  const { activities, activitiesCount, activitiesLoading, activitiesError, swrKey } =
    useGetTodoActivities({ scope, window, page, pageSize: validPageSize });

  const handlePaginationChange = useCallback(
    ({ page: newPage, pageSize: newSize }) => {
      setPage(newPage);
      const size = Number(newSize);
      if (!Number.isNaN(size) && size > 0 && size !== validPageSize) setPageSize(size);
    },
    [setPageSize, validPageSize],
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
    />
  );
}

RepActivityTable.propTypes = {
  window: PropTypes.string,
  scope: PropTypes.string,
};
