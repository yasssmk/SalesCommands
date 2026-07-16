// frontend/src/sections/home/TodoActivityTable.jsx

'use client';

import PropTypes from 'prop-types';
import { useMemo } from 'react';
import { useRouter } from 'next/navigation';

import Typography from '@mui/material/Typography';

import ReusableTable from 'components/table/Table';

// ==============================|| TODO ACTIVITY TABLE — shared navigation-only todo rows ||============================== //
//
// The presentational core shared by the rep todo table and the manager team
// todo table: the entity-link columns (activity / account / DC / campaign) to
// the verified routes, plus the ReusableTable wiring. Callers own the data hook,
// pagination, sorting (server-side, mapped to `ordering`) and search state and
// pass them in; `leadingColumns` lets a caller prepend columns (the manager adds
// Person + Team). Advanced-filter props are forwarded straight to ReusableTable
// (the manager wires the standard filter panel + chips).

// A navigable entity: default text color, primary + underline on HOVER only —
// the repo's link convention (matches ActivityTable / accounts list). Non-link
// values (Person, Team) are plain <Typography>, never wrapped in LinkCell.
export function LinkCell({ label, onClick }) {
  return (
    <Typography
      variant="body2"
      sx={{ cursor: 'pointer', '&:hover': { color: 'primary.main', textDecoration: 'underline' } }}
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
 * Renders todo rows. Every entity cell is its own link to the verified route;
 * pagination/sorting/search are server-side and owned by the caller. Only the
 * columns the backend can order (Account, Due — plus a manager's Person) are
 * sortable; the rest set enableSorting:false so the "Sort by" control lists only
 * what the server actually supports.
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
  sorting = [],
  onSortingChange,
  onSearchChange,
  leadingColumns = [],
  emptyDescription = 'No activities in this window.',
  searchPlaceholder = 'Search todo…',
  // Advanced filter panel (manager): forwarded to ReusableTable.
  advancedFilterPanel = null,
  advancedFilters = [],
  advancedFilterCount = 0,
  onAdvancedFilterOpen,
  onAdvancedFilterRemove,
  onAdvancedFilterClear,
}) {
  const router = useRouter();

  const columns = useMemo(
    () => [
      ...leadingColumns,
      {
        header: 'Activity',
        id: 'title', // -> title (server ordering)
        accessorKey: 'title',
        cell: ({ row }) => (
          <LinkCell
            label={row.original.title || 'Untitled'}
            onClick={() => router.push(`/activities/${row.original.id}`)}
          />
        ),
      },
      {
        header: 'Type',
        id: 'activity_type', // -> activity_type (server ordering; display is the label)
        accessorKey: 'activity_type_display',
        cell: ({ getValue }) => <Typography variant="body2">{getValue() || '—'}</Typography>,
      },
      {
        header: 'Account',
        id: 'account', // -> account__company_name
        // accessorFn is REQUIRED for the column to be sortable: TanStack's
        // getCanSort() gates on !!column.accessorFn, so a display column (id +
        // cell only) is never sortable — even in manualSorting. The value must
        // mirror what the server orders by (account__company_name) so a reader
        // never mistakes this for client-side sorting; sorting stays server-side.
        accessorFn: (row) => row.account?.company_name || '',
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
        // The NATURE of the link — repo vocabulary for an activity's cycle/campaign.
        header: 'Context',
        id: 'context', // -> context_kind
        // accessorFn -> sortable (see Account). context_kind is the server's
        // Decision-Cycle-vs-Campaign ordering key; mirror it here.
        accessorFn: (row) => (row.decision_cycle ? 'Decision Cycle' : row.campaign ? 'Campaign' : ''),
        cell: ({ row }) => {
          const { decision_cycle: dc, campaign } = row.original;
          const kind = dc ? 'Decision Cycle' : campaign ? 'Campaign' : null;
          return kind ? <Typography variant="body2">{kind}</Typography> : <Muted />;
        },
      },
      {
        // The NAME of that cycle/campaign — the clickable link to its route.
        header: 'Name',
        id: 'name', // -> context_name = COALESCE(dc.name, campaign.name)
        // accessorFn -> sortable (see Account). Mirror the server's
        // context_name = COALESCE(dc.name, campaign.name).
        accessorFn: (row) => row.decision_cycle?.name || row.campaign?.name || '',
        cell: ({ row }) => {
          const { account, decision_cycle: dc, campaign } = row.original;
          if (dc) {
            return account ? (
              <LinkCell
                label={dc.name || 'Decision cycle'}
                onClick={() => router.push(`/accounts/${account.id}/dc/${dc.id}`)}
              />
            ) : (
              <Typography variant="body2">{dc.name || 'Decision cycle'}</Typography>
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
        id: 'effective_date', // -> effective_date (server ordering; default asc)
        accessorKey: 'effective_date',
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
      onSortingChange={onSortingChange}
      onSearchChange={onSearchChange}
      showAddButton={false}
      enableImport={false}
      searchPlaceholder={searchPlaceholder}
      emptyMessage="Nothing here"
      emptyDescription={emptyDescription}
      advancedFilterPanel={advancedFilterPanel}
      advancedFilters={advancedFilters}
      advancedFilterCount={advancedFilterCount}
      onAdvancedFilterOpen={onAdvancedFilterOpen}
      onAdvancedFilterRemove={onAdvancedFilterRemove}
      onAdvancedFilterClear={onAdvancedFilterClear}
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
  sorting: PropTypes.array,
  onSortingChange: PropTypes.func,
  onSearchChange: PropTypes.func,
  leadingColumns: PropTypes.array,
  emptyDescription: PropTypes.string,
  searchPlaceholder: PropTypes.string,
  advancedFilterPanel: PropTypes.node,
  advancedFilters: PropTypes.array,
  advancedFilterCount: PropTypes.number,
  onAdvancedFilterOpen: PropTypes.func,
  onAdvancedFilterRemove: PropTypes.func,
  onAdvancedFilterClear: PropTypes.func,
};
