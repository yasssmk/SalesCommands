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

// hooks
import useLocalStorage from 'hooks/useLocalStorage';
import { useAuth } from 'hooks/useAuth';

// api
import { 
  useGetActivitiesByAccount,
  cancelActivity
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
  const [activityToEdit, setActivityToEdit] = useState(null);
  
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [activityToDelete, setActivityToDelete] = useState(null);
  
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [activityToComplete, setActivityToComplete] = useState(null);

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
    setActivityToEdit(null);
    setActivityModalOpen(true);
  }, []);

  const handleEdit = useCallback((activity) => {
    setActivityToEdit(activity);
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

  const handleCancel = useCallback(async (activity) => {
  if (!activity?.id) return;
  
  try {
    const result = await cancelActivity(activity.id, { notes: 'Cancelled by user' });
    
    if (result.success) {
      displaySuccessSnackbar('Activity cancelled');
      mutateActivities();
    } else {
      displayErrorSnackbar({
        message: result.error || 'Failed to cancel activity',
        status: result.status
      });
    }
  } catch (err) {
    displayErrorSnackbar({
      message: err?.message || 'An unexpected error occurred',
      status: 500
    });
  }
}, [mutateActivities]);

  // ==============================|| HANDLERS - MODAL CLOSE ||============================== //

  const handleActivityModalClose = useCallback(() => {
    setActivityModalOpen(false);
    setActivityToEdit(null);
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
        onEdit={handleEdit}
        onDelete={handleDelete}
        onComplete={handleComplete}
        onCancel={handleCancel}
        showAccount={false}
        emptyMessage="No activities yet"
        emptyDescription="Create your first activity to start tracking your sales actions for this account"
      />

      {/* Activity Modal (Create/Edit) */}
      <ActivityModal
        open={activityModalOpen}
        onClose={handleActivityModalClose}
        activity={activityToEdit}
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