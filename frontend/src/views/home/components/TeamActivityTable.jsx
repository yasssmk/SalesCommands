// frontend/src/views/home/components/TeamActivityTable.jsx

'use client';

import PropTypes from 'prop-types';
import { useCallback, useEffect, useMemo, useState } from 'react';

import Typography from '@mui/material/Typography';

import useLocalStorage from 'hooks/useLocalStorage';
import { useGetTeamTodoActivities } from 'api/bi/todo';

import TodoActivityTable from './TodoActivityTable';

// ==============================|| TEAM ACTIVITY TABLE — the manager's team todo rows ||============================== //

/**
 * The manager view's team todo rows, from /bi/todo/team/. A thin wrapper over
 * the shared TodoActivityTable that adds a leading "Person" column (the owner —
 * who the task belongs to) and owns page state + persisted page size. Narrowable
 * to a team subtree (team) and/or a single person (owner) — changing either is a
 * new list, so the page resets. Security is server-side (role scope); team/owner
 * are display-only narrowing.
 */
export default function TeamActivityTable({ team, owner }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage('teamActivityTablePageSize', 10);
  const validPageSize = Number(pageSize) > 0 ? Number(pageSize) : 10;

  // A new team/person is a new list — back to page 1.
  useEffect(() => {
    setPage(1);
  }, [team, owner]);

  const { activities, activitiesCount, activitiesLoading, activitiesError, swrKey } =
    useGetTeamTodoActivities({ scope: 'team', team, owner, page, pageSize: validPageSize });

  const handlePaginationChange = useCallback(
    ({ page: newPage, pageSize: newSize }) => {
      setPage(newPage);
      const size = Number(newSize);
      if (!Number.isNaN(size) && size > 0 && size !== validPageSize) setPageSize(size);
    },
    [setPageSize, validPageSize],
  );

  const leadingColumns = useMemo(
    () => [
      {
        header: 'Person',
        id: 'owner',
        enableSorting: false,
        cell: ({ row }) => {
          const o = row.original.owner;
          return (
            <Typography variant="body2">{o?.full_name || o?.email || '—'}</Typography>
          );
        },
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
      leadingColumns={leadingColumns}
      emptyDescription="No open tasks for this selection."
    />
  );
}

TeamActivityTable.propTypes = {
  team: PropTypes.string,
  owner: PropTypes.string,
};
