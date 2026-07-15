// frontend/src/views/home/components/RepActivityTable.jsx

'use client';

import PropTypes from 'prop-types';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import Typography from '@mui/material/Typography';

import ReusableTable from 'components/table/Table';
import useLocalStorage from 'hooks/useLocalStorage';
import { useGetTodoActivities } from 'api/bi/todo';

// ==============================|| REP ACTIVITY TABLE — navigation-only todo list ||============================== //

function LinkCell({ label, onClick }) {
  return (
    <Typography
      variant="body2"
      sx={{ cursor: 'pointer', color: 'primary.main', '&:hover': { textDecoration: 'underline' } }}
      onClick={(event) => {
        // Each entity is its own link; stop the cell click from bubbling.
        event.stopPropagation();
        onClick();
      }}
    >
      {label}
    </Typography>
  );
}

LinkCell.propTypes = { label: PropTypes.string, onClick: PropTypes.func };

function Muted() {
  return (
    <Typography variant="body2" color="text.secondary">
      —
    </Typography>
  );
}

function formatDue(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString();
}

/**
 * The rep's todo rows for the active window. Reuses ReusableTable (no
 * select/Actions columns — navigation only): every entity cell is its own link
 * (activity / account / DC / campaign), with the verified routes. Page size is
 * persisted; the page resets when the window filter changes.
 */
export default function RepActivityTable({ window, scope = 'mine' }) {
  const router = useRouter();
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

  const columns = useMemo(
    () => [
      {
        header: 'Activity',
        accessorKey: 'title',
        enableSorting: false,
        cell: ({ row }) => (
          <LinkCell
            label={row.original.title || 'Untitled'}
            onClick={() => router.push(`/activities/${row.original.id}`)}
          />
        ),
      },
      {
        header: 'Type',
        accessorKey: 'activity_type_display',
        enableSorting: false,
        cell: ({ getValue }) => <Typography variant="body2">{getValue() || '—'}</Typography>,
      },
      {
        header: 'Account',
        id: 'account',
        enableSorting: false,
        cell: ({ row }) => {
          const acc = row.original.account;
          return acc ? (
            <LinkCell label={acc.company_name || 'Account'} onClick={() => router.push(`/accounts/${acc.id}`)} />
          ) : (
            <Muted />
          );
        },
      },
      {
        header: 'Decision cycle / Campaign',
        id: 'context',
        enableSorting: false,
        cell: ({ row }) => {
          const { account, decision_cycle: dc, campaign } = row.original;
          if (dc && account) {
            return (
              <LinkCell
                label={dc.name || 'Decision cycle'}
                onClick={() => router.push(`/accounts/${account.id}/dc/${dc.id}`)}
              />
            );
          }
          if (campaign) {
            return (
              <LinkCell label={campaign.name || 'Campaign'} onClick={() => router.push(`/campaigns/${campaign.id}`)} />
            );
          }
          return <Muted />;
        },
      },
      {
        header: 'Due',
        accessorKey: 'effective_date',
        enableSorting: false,
        cell: ({ row }) => (
          <Typography variant="body2">{formatDue(row.original.effective_date || row.original.due_date)}</Typography>
        ),
      },
    ],
    [router],
  );

  return (
    <ReusableTable
      data={activities}
      columns={columns}
      loading={activitiesLoading}
      error={activitiesError}
      swrKey={swrKey}
      totalCount={activitiesCount}
      currentPage={page}
      onPaginationChange={handlePaginationChange}
      initialPageSize={validPageSize}
      showAddButton={false}
      searchPlaceholder="Search todo…"
      emptyMessage="Nothing here"
      emptyDescription="No activities in this window."
    />
  );
}

RepActivityTable.propTypes = {
  window: PropTypes.string,
  scope: PropTypes.string,
};
