// frontend/src/sections/territories/workspace/TerritoryActivitiesTab.jsx
/**
 * Territory Activities Tab Component
 * 
 * Displays activities for accounts in a territory.
 * Uses ActivityTable with showAccount=true.
 * 
 * Implementation:
 * 1. Fetches accounts belonging to the territory
 * 2. Fetches activities and filters client-side by territory account IDs
 * 
 * Note: For better performance with large datasets, consider adding
 * a backend endpoint that supports filtering by multiple account IDs.
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback, useMemo } from 'react';

// material-ui
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import ActivityTable, { COLUMN_TO_BACKEND_FIELD } from 'sections/accounts/activities/ActivityTable';
import ActivityModal from 'sections/accounts/activities/ActivityModal';
import ActivityCompleteModal from 'sections/accounts/activities/ActivityCompleteModal';
import AlertActivityDelete from 'sections/accounts/activities/AlertActivityDelete';

// hooks
import useLocalStorage from 'hooks/useLocalStorage';
import { useAuth } from 'hooks/useAuth';

// api
import { 
  useGetActivities,
  cancelActivity
} from 'api/accounts/activities';
import { useGetAccounts } from 'api/admin/accounts';
import { tenantKey } from 'api/_swr';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| TERRITORY ACTIVITIES TAB ||============================== //

/**
 * TerritoryActivitiesTab Component
 * 
 * Displays activities for a territory.
 * For MVP, displays all activities (territory filtering will be added later).
 * 
 * @param {Object} props
 * @param {string} props.territoryId - UUID of the territory
 * @param {Object} props.territory - Territory data
 */
export default function TerritoryActivitiesTab({ territoryId, territory }) {
  const { tenantId } = useAuth();

  // ==============================|| PAGINATION STATE ||============================== //

  const [pageSize, setPageSize] = useLocalStorage('territoryActivitiesPageSize', 25);
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

  // Step 1: Fetch accounts belonging to this territory
  const {
    accounts: territoryAccounts,
    accountsLoading: accountsLoading
  } = useGetAccounts({
    page: 1,
    pageSize: 500, // Get all accounts in territory
    filters: { territory_id: territoryId }
  });

  // Extract account IDs from territory
  const territoryAccountIds = useMemo(() => {
    if (!territoryAccounts || territoryAccounts.length === 0) return [];
    return territoryAccounts.map(account => account.id);
  }, [territoryAccounts]);

  // Step 2: Fetch activities (larger batch for client-side filtering)
  // Note: We fetch more than pageSize because we filter client-side
  const {
    activities: allActivities,
    activitiesLoading: activitiesDataLoading,
    activitiesError,
    mutateActivities
  } = useGetActivities({
    page: 1,
    pageSize: 500, // Fetch larger batch for client-side filtering
    ordering,
    search,
    filters: {}
  });

  // Filter activities to only those belonging to territory accounts
  const filteredActivities = useMemo(() => {
    if (!allActivities || territoryAccountIds.length === 0) return [];
    return allActivities.filter(activity => 
      activity.account?.id && territoryAccountIds.includes(activity.account.id)
    );
  }, [allActivities, territoryAccountIds]);

  // Apply client-side pagination
  const activities = useMemo(() => {
    const startIndex = (page - 1) * validPageSize;
    const endIndex = startIndex + validPageSize;
    return filteredActivities.slice(startIndex, endIndex);
  }, [filteredActivities, page, validPageSize]);

  // Total count is the filtered count
  const activitiesCount = filteredActivities.length;
  
  // Combined loading state
  const activitiesLoading = accountsLoading || activitiesDataLoading;

  // SWR key for revalidation
  const swrKey = tenantKey('/module-activities/', tenantId);

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

  // No add from territory view - activities are created from account context
  const handleAdd = null;

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
        displayErrorSnackbar(result);
      }
    } catch (error) {
      displayErrorSnackbar(error);
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

  // Show loading while fetching accounts
  if (accountsLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  // Show message if no accounts in territory
  if (territoryAccountIds.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 6 }}>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          No accounts in this territory
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Add accounts to this territory to see their activities
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Activities Table - showAccount=true for territory view */}
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
        showAccount={true}
        emptyMessage="No activities in this territory"
        emptyDescription="Create activities from account workspaces to see them here"
      />

      {/* Activity Modal (Edit only - no create from territory) */}
      {activityModalOpen && activityToEdit && (
        <ActivityModal
          open={activityModalOpen}
          onClose={handleActivityModalClose}
          activity={activityToEdit}
          accountId={activityToEdit?.account?.id}
          onSuccess={handleActivitySuccess}
        />
      )}

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

TerritoryActivitiesTab.propTypes = {
  territoryId: PropTypes.string.isRequired,
  territory: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string
  })
};