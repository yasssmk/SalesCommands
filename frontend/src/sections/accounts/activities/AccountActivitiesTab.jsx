// frontend/src/sections/accounts/activities/AccountActivitiesTab.jsx
/**
 * Account Activities Tab Component
 * 
 * Main tab content for Activities in Account Workspace.
 * Displays activities list with CRUD operations.
 * 
 * Features:
 * - Activities table with pagination/search/sorting
 * - Create/Edit/Delete activities
 * - Complete/Cancel activity actions
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback, useMemo } from 'react';

// material-ui
import Box from '@mui/material/Box';

// project imports
import ActivityTable, { COLUMN_TO_BACKEND_FIELD } from './ActivityTable';
import ActivityModal from './ActivityModal';
import ActivityCompleteModal from './ActivityCompleteModal';
import AlertActivityDelete from './AlertActivityDelete';
import AlertActivityCancel from './AlertActivityCancel';
import AlertActivityReopen from 'sections/accounts/activities/AlertActivityReopen';

// hooks
import useLocalStorage from 'hooks/useLocalStorage';
import { useAuth } from 'hooks/useAuth';

// api
import { 
  useGetActivitiesByAccount,
} from 'api/accounts/activities';
import { tenantKey } from 'api/_swr';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| ACCOUNT ACTIVITIES TAB ||============================== //

/**
 * AccountActivitiesTab Component
 * 
 * @param {string} accountId - Account UUID
 * @param {Object} account - Account data
 */
export default function AccountActivitiesTab({ accountId, account }) {
  const { tenantId } = useAuth();

  // ==============================|| PAGINATION STATE ||============================== //

  const [pageSize, setPageSize] = useLocalStorage('accountActivitiesPageSize', 25);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sorting, setSorting] = useState([{ id: 'scheduled_date', desc: true }]);

  // Validate page size
  const validPageSize = useMemo(() => {
    const size = Number(pageSize);
    return [10, 25, 50, 100].includes(size) ? size : 25;
  }, [pageSize]);

  // Build ordering string for API
  const ordering = useMemo(() => {
    if (!sorting.length) return '-scheduled_date';
    const sort = sorting[0];
    const backendField = COLUMN_TO_BACKEND_FIELD[sort.id] || sort.id;
    return sort.desc ? `-${backendField}` : backendField;
  }, [sorting]);

  // ==============================|| MODAL STATE ||============================== //

  const [activityModalOpen, setActivityModalOpen] = useState(false);  
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [activityToDelete, setActivityToDelete] = useState(null);
  
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [activityToComplete, setActivityToComplete] = useState(null);

  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [activityToCancel, setActivityToCancel] = useState(null);

  const [reopenModalOpen, setReopenModalOpen] = useState(false);
  const [activityToReopen, setActivityToReopen] = useState(null);

  // ==============================|| DATA FETCHING ||============================== //

  const {
    activities,
    activitiesCount,
    activitiesLoading,
    activitiesError,
    mutateActivities
  } = useGetActivitiesByAccount(accountId, {
    page,
    pageSize: validPageSize,
    ordering,
    filters: {}
  });

  // SWR key for revalidation
  const swrKey = tenantKey(`/module-activities/by-account/?account_id=${accountId}`, tenantId);

  // ==============================|| HANDLERS - PAGINATION ||============================== //

  const handlePaginationChange = useCallback(({ page: newPage, pageSize: newPageSize }) => {
    setPage(newPage);
    if (newPageSize !== validPageSize) {
      setPageSize(newPageSize);
    }
  }, [validPageSize, setPageSize]);

  const handleSearchChange = useCallback((value) => {
    setSearch(value);
    setPage(1);
  }, []);

  const handleSortingChange = useCallback((newSorting) => {
    setSorting(newSorting);
    setPage(1);
  }, []);

  // ==============================|| HANDLERS - CRUD ||============================== //

  const handleAdd = useCallback(() => {
    setActivityModalOpen(true);
  }, []);

  const handleDelete = useCallback((activity) => {
    setActivityToDelete(activity);
    setDeleteModalOpen(true);
  }, []);

  const handleComplete = useCallback((activity) => {
    setActivityToComplete(activity);
    setCompleteModalOpen(true);
  }, []);

  const handleCancel = useCallback((activity) => {
    setActivityToCancel(activity);
    setCancelModalOpen(true);
  }, []);

  const handleCancelModalClose = useCallback(() => {
    setCancelModalOpen(false);
    setActivityToCancel(null);
  }, []);

  const handleCancelSuccess = useCallback(() => {
    setCancelModalOpen(false);
    setActivityToCancel(null);
    mutateActivities();
  }, [mutateActivities]);

  const handleReopen = useCallback((activity) => {
    setActivityToReopen(activity);
    setReopenModalOpen(true);
  }, []);

  const handleReopenModalClose = useCallback(() => {
    setReopenModalOpen(false);
    setActivityToReopen(null);
  }, []);

  const handleReopenSuccess = useCallback(() => {
    setReopenModalOpen(false);
    setActivityToReopen(null);
    mutateActivities();
  }, [mutateActivities]);

  // ==============================|| HANDLERS - MODAL CLOSE ||============================== //

  const handleActivityModalClose = useCallback(() => {
    setActivityModalOpen(false);
  }, []);

  const handleDeleteModalClose = useCallback(() => {
    setDeleteModalOpen(false);
    setActivityToDelete(null);
  }, []);

  const handleCompleteModalClose = useCallback(() => {
    setCompleteModalOpen(false);
    setActivityToComplete(null);
  }, []);

  // ==============================|| HANDLERS - SUCCESS ||============================== //

  const handleActivitySuccess = useCallback(() => {
    mutateActivities();
  }, [mutateActivities]);

  const handleDeleteSuccess = useCallback(() => {
    mutateActivities();
  }, [mutateActivities]);

  const handleCompleteSuccess = useCallback(() => {
    mutateActivities();
  }, [mutateActivities]);

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      {/* Activities Table */}
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
        onDelete={handleDelete}
        onComplete={handleComplete}
        onCancel={handleCancel}
        onReopen={handleReopen}
        showAccount={false}
        emptyMessage="No activities yet"
        emptyDescription="Create your first activity to start tracking your sales actions for this account"
      />

      {/* Activity Modal (Create/Edit) */}
      <ActivityModal
        open={activityModalOpen}
        onClose={handleActivityModalClose}
        activity={null}
        accountId={accountId}
        onSuccess={handleActivitySuccess}
      />

      {/* Complete Modal */}
      {completeModalOpen && (
        <ActivityCompleteModal
          open={completeModalOpen}
          onClose={handleCompleteModalClose}
          activity={activityToComplete}
          onSuccess={handleCompleteSuccess}
        />
      )}

      {/* Cancel Confirmation */}
      <AlertActivityCancel
        open={cancelModalOpen}
        handleClose={handleCancelModalClose}
        activity={activityToCancel}
        onSuccess={handleCancelSuccess}
      />

      {/* Reopen Confirmation */}
      <AlertActivityReopen
        open={reopenModalOpen}
        handleClose={handleReopenModalClose}
        activity={activityToReopen}
        onSuccess={handleReopenSuccess}
      />

      {/* Delete Confirmation */}
      <AlertActivityDelete
        open={deleteModalOpen}
        onClose={handleDeleteModalClose}
        activity={activityToDelete}
        onSuccess={handleDeleteSuccess}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

AccountActivitiesTab.propTypes = {
  accountId: PropTypes.string.isRequired,
  account: PropTypes.object
};