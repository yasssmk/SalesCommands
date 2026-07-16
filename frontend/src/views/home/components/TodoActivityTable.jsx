// frontend/src/views/home/components/TodoActivityTable.jsx

'use client';

import PropTypes from 'prop-types';
import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import Typography from '@mui/material/Typography';

import ReusableTable from 'components/table/Table';

// ==============================|| TODO ACTIVITY TABLE — shared navigation-only todo rows ||============================== //
//
// The presentational core shared by the rep todo table and the manager team
// todo table: the entity-link columns (activity / account / DC / campaign) to
// the verified routes, plus the ReusableTable wiring (navigation only — no
// select/Actions columns). Callers own the data hook + pagination state and
// pass the rows in; `leadingColumns` lets a caller prepend columns (the manager
// adds a "Person" column) without duplicating the base column set.

export function LinkCell({ label, onClick }) {
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
 * Renders todo rows for a window/scope. Every entity cell is its own link to the
 * verified route; pagination is manual (the caller owns page + page size).
 */
export default function TodoActivityTable({
  activities,
  activitiesCount,
  activitiesLoading,
  activitiesError,
  swrKey,
  page,
  onPaginationChange,
  pageSize,
  leadingColumns = [],
  emptyDescription = 'No activities in this window.',
}) {
  const router = useRouter();

  // ReusableTable runs TanStack in manual mode: the sorting state belongs to the
  // caller (an undefined `sorting` overrides TanStack's default and crashes
  // getSortedRowModel on `getState().sorting.length`). These rows are sorted
  // server-side by effective_date and the columns are non-sortable, so this is a
  // stable empty state — present for the contract, never mutated by the user.
  const [sorting, setSorting] = useState([]);

  const columns = useMemo(
    () => [
      ...leadingColumns,
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
    [router, leadingColumns],
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
      onPaginationChange={onPaginationChange}
      initialPageSize={pageSize}
      sorting={sorting}
      onSortingChange={setSorting}
      showAddButton={false}
      searchPlaceholder="Search todo…"
      emptyMessage="Nothing here"
      emptyDescription={emptyDescription}
    />
  );
}

TodoActivityTable.propTypes = {
  activities: PropTypes.array,
  activitiesCount: PropTypes.number,
  activitiesLoading: PropTypes.bool,
  activitiesError: PropTypes.any,
  swrKey: PropTypes.any,
  page: PropTypes.number,
  onPaginationChange: PropTypes.func,
  pageSize: PropTypes.number,
  leadingColumns: PropTypes.array,
  emptyDescription: PropTypes.string,
};
