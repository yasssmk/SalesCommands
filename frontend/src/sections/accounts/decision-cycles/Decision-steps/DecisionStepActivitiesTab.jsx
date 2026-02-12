// frontend/src/sections/accounts/decision-cycles/Decision-steps/DecisionStepActivitiesTab.jsx
/**
 * Decision Step Activities Tab
 *
 * Read-only ActivityTable showing activities linked to this step.
 * Uses the shared ActivityTable component (same as Account/Territory).
 *
 * - No edit/delete/complete/cancel/reopen actions (read-only)
 * - Add Activity button opens ActivityModal
 * - Click row navigates to activity workspace
 * - Server-side pagination, search, sorting
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback, useMemo } from 'react';

// MUI
import Box from '@mui/material/Box';

// Project imports
import ActivityTable, { COLUMN_TO_BACKEND_FIELD } from 'sections/accounts/activities/ActivityTable';
import ActivityModal from 'sections/accounts/activities/ActivityModal';

// Hooks
import useLocalStorage from 'hooks/useLocalStorage';

// API
import { useGetActivitiesByStep } from 'api/accounts/activities';

// ==============================|| DECISION STEP ACTIVITIES TAB ||============================== //

/**
 * @param {Object} step - Decision Step data
 * @param {string} accountId - Account UUID
 * @param {Function} onUpdate - Callback to refresh step data after create
 */
export default function DecisionStepActivitiesTab({ step, accountId, onUpdate }) {

  // ==============================|| PAGINATION STATE ||============================== //

  const [pageSize, setPageSize] = useLocalStorage('stepActivitiesPageSize', 25);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sorting, setSorting] = useState([{ id: 'scheduled_date', desc: true }]);

  const validPageSize = useMemo(() => {
    const size = Number(pageSize);
    return [10, 25, 50, 100].includes(size) ? size : 25;
  }, [pageSize]);

  const ordering = useMemo(() => {
    if (!sorting.length) return '-scheduled_date';
    const sort = sorting[0];
    const backendField = COLUMN_TO_BACKEND_FIELD[sort.id] || sort.id;
    return sort.desc ? `-${backendField}` : backendField;
  }, [sorting]);

  // ==============================|| DATA FETCHING ||============================== //

  const {
    activities,
    activitiesCount,
    activitiesLoading,
    activitiesError,
    mutateActivities
  } = useGetActivitiesByStep(step?.id, {
    page,
    pageSize: validPageSize,
    ordering,
    search
  });

  // ==============================|| MODAL STATE ||============================== //

  const [activityModalOpen, setActivityModalOpen] = useState(false);

  // ==============================|| HANDLERS ||============================== //

  const handlePaginationChange = useCallback(({ pageIndex, pageSize: newPageSize }) => {
    setPage(pageIndex + 1);
    if (newPageSize !== validPageSize) {
      setPageSize(newPageSize);
    }
  }, [validPageSize, setPageSize]);

  const handleSearchChange = useCallback((value) => {
    setSearch(value);
    setPage(1);
  }, []);

  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting((prevSorting) =>
      typeof updaterOrValue === 'function'
        ? updaterOrValue(prevSorting)
        : updaterOrValue
    );
  }, []);

  const handleAdd = useCallback(() => {
    setActivityModalOpen(true);
  }, []);

  const handleModalClose = useCallback(() => {
    setActivityModalOpen(false);
  }, []);

  const handleModalSuccess = useCallback(() => {
    setActivityModalOpen(false);
    mutateActivities();
    onUpdate?.();
  }, [mutateActivities, onUpdate]);

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      <ActivityTable
        activities={activities}
        loading={activitiesLoading}
        error={activitiesError}
        totalCount={activitiesCount}
        page={page}
        pageSize={validPageSize}
        sorting={sorting}
        onPaginationChange={handlePaginationChange}
        onSearchChange={handleSearchChange}
        onSortingChange={handleSortingChange}
        onAdd={handleAdd}
        showAccount={false}
        showActions={false}
        emptyMessage="No activities yet"
        emptyDescription="Create activities to track meetings, calls, emails, and tasks for this step."
      />

      {/* Activity Modal (Create only) */}
      <ActivityModal
        open={activityModalOpen}
        onClose={handleModalClose}
        activity={null}
        accountId={accountId}
        decisionCycleId={step?.cycle_id || step?.cycle}
        decisionStepId={step?.id}
        onSuccess={handleModalSuccess}
      />
    </Box>
  );
}

DecisionStepActivitiesTab.propTypes = {
  step: PropTypes.object,
  accountId: PropTypes.string,
  onUpdate: PropTypes.func
};