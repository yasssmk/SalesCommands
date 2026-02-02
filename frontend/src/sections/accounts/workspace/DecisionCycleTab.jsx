// frontend/src/sections/accounts/workspace/DecisionCycleTab.jsx
/**
 * Decision Cycle Tab Component
 * 
 * Main tab content for Decision Cycle (Pipeline) in Account Workspace.
 * Orchestrates all decision cycle components.
 * 
 * ARCHITECTURE UPDATE:
 * - Pipeline steps are FIXED and auto-created (no manual step creation)
 * - Users add ACTIVITIES within steps, not steps themselves
 * - Click on step header → Step Workspace
 * - Click on activity card → Activity Workspace
 * 
 * Features:
 * - Cycle selector at top
 * - Pipeline view with steps as columns, activities as cards
 * - Empty state when no cycles
 * - Modal for create/edit cycle
 * - Modal for create activity (within a step)
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';

// material-ui
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';

// project imports
import DecisionCycleSelector from '../decision-cycles/DecisionCycleSelector';
import DecisionCycleTimeline from '../decision-cycles/DecisionCycleTimeline';
import DecisionCycleEmpty from '../decision-cycles/DecisionCycleEmpty';
import DecisionCycleModal from '../decision-cycles/DecisionCycleModal';
import ActivityModal from '../activities/ActivityModal';

import { 
  useGetDecisionCyclesByAccount,
  useGetDecisionCycle,
  deleteDecisionCycle
} from 'api/accounts/decisionCycles';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| DECISION CYCLE TAB ||============================== //

/**
 * DecisionCycleTab Component
 * 
 * @param {string} accountId - Account UUID
 * @param {string} accountName - Account name (for display)
 */
export default function DecisionCycleTab({ accountId, accountName }) {
  
  const router = useRouter();

  // ==============================|| STATE ||============================== //
  
  // Selected cycle ID
  const [selectedCycleId, setSelectedCycleId] = useState(null);
  
  // Cycle Modal state (Create/Edit)
  const [cycleModalOpen, setCycleModalOpen] = useState(false);
  const [cycleToEdit, setCycleToEdit] = useState(null);
  
  // Activity Modal state (Create within step)
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [activityTargetStep, setActivityTargetStep] = useState(null);
  
  // ==============================|| DATA FETCHING ||============================== //
  
  // Fetch all cycles for this account
  const { 
    cycles, 
    cyclesLoading, 
    mutateCycles 
  } = useGetDecisionCyclesByAccount(accountId);
  
  // Determine current cycle (selected or first active)
  const currentCycleId = useMemo(() => {
    if (selectedCycleId) return selectedCycleId;
    if (!cycles || cycles.length === 0) return null;
    
    // Find active cycle or first one
    const activeCycle = cycles.find(c => c.is_active);
    return activeCycle?.id || cycles[0]?.id;
  }, [selectedCycleId, cycles]);
  
  // Fetch current cycle details with steps (and their activities)
  const { 
    cycle: currentCycle, 
    cycleLoading: currentCycleLoading,
    mutateCycle 
  } = useGetDecisionCycle(currentCycleId);
  
  // ==============================|| CYCLE HANDLERS ||============================== //
  
  const handleCycleChange = useCallback((cycle) => {
    setSelectedCycleId(cycle.id);
  }, []);
  
  const handleCreateCycle = useCallback(() => {
    setCycleToEdit(null);
    setCycleModalOpen(true);
  }, []);
  
  const handleEditCycle = useCallback((cycle) => {
    setCycleToEdit(cycle);
    setCycleModalOpen(true);
  }, []);
  
  const handleDeleteCycle = useCallback(async (cycle) => {
    if (!cycle?.id) return;
    
    // Confirm deletion
    if (!window.confirm(`Are you sure you want to delete "${cycle.name}"? This will also delete all steps and activities.`)) {
      return;
    }
    
    try {
      // IMPORTANT: Clear selection FIRST to prevent 404 refetch
      const wasSelected = selectedCycleId === cycle.id;
      if (wasSelected) {
        setSelectedCycleId(null);
      }
      
      // Now delete (cache will be cleared, no auto-revalidation)
      const result = await deleteDecisionCycle(cycle.id);
      
      if (result.success) {
        displaySuccessSnackbar('Decision cycle deleted successfully');
        // NOW revalidate cycles list (after selection is cleared)
        mutateCycles();
      } else {
        displayErrorSnackbar({
          message: result.error || 'Failed to delete decision cycle',
          status: result.status
        });
        // Restore selection if delete failed
        if (wasSelected) {
          setSelectedCycleId(cycle.id);
        }
      }
    } catch (err) {
      displayErrorSnackbar({
        message: err?.message || 'An unexpected error occurred',
        status: 500
      });
    }
  }, [selectedCycleId, mutateCycles]);
  
  const handleCycleModalClose = useCallback(() => {
    setCycleModalOpen(false);
    setCycleToEdit(null);
  }, []);
  
  const handleCycleSuccess = useCallback((data) => {
    mutateCycles();
    
    // Select newly created cycle
    if (!cycleToEdit && data?.id) {
      setSelectedCycleId(data.id);
    }
    
    // Revalidate current cycle if editing
    if (cycleToEdit) {
      mutateCycle();
    }
  }, [cycleToEdit, mutateCycles, mutateCycle]);
  
  // ==============================|| PIPELINE HANDLERS ||============================== //
  
  /**
   * Handle click on step header → Navigate to Step Workspace
   * Route: /accounts/{accountId}/decisionSteps/{stepId}
   */
  const handleStepClick = useCallback((step) => {
    router.push(`/accounts/${accountId}/decisionSteps/${step.id}`);
  }, [router, accountId]);
  
  /**
   * Handle click on activity card → Navigate to Activity Workspace
   * Route: /activities/{activityId}
   */
  const handleActivityClick = useCallback((activity) => {
    router.push(`/activities/${activity.id}`);
  }, [router]);
  
  /**
   * Handle "Add Activity" button click in a step column
   * Opens ActivityModal with step pre-selected
   */
  const handleAddActivity = useCallback((step) => {
    setActivityTargetStep(step);
    setActivityModalOpen(true);
  }, []);
  
  /**
   * Handle Activity Modal close
   */
  const handleActivityModalClose = useCallback(() => {
    setActivityModalOpen(false);
    setActivityTargetStep(null);
  }, []);
  
  /**
   * Handle Activity creation success
   */
  const handleActivitySuccess = useCallback(() => {
    // Revalidate cycle to refresh activities in steps
    mutateCycle();
    handleActivityModalClose();
  }, [mutateCycle, handleActivityModalClose]);
  
  // ==============================|| LOADING STATE ||============================== //
  
  if (cyclesLoading) {
    return (
      <Box 
        sx={{ 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center', 
          minHeight: 300 
        }}
      >
        <CircularProgress />
      </Box>
    );
  }
  
  // ==============================|| EMPTY STATE ||============================== //
  
  if (!cycles || cycles.length === 0) {
    return (
      <>
        <DecisionCycleEmpty 
          onCreateCycle={handleCreateCycle} 
          accountName={accountName}
        />
        
        <DecisionCycleModal
          open={cycleModalOpen}
          onClose={handleCycleModalClose}
          cycle={null}
          accountId={accountId}
          onSuccess={handleCycleSuccess}
        />
      </>
    );
  }
  
  // ==============================|| MAIN RENDER ||============================== //
  
  return (
    <Box>
      {/* Cycle Selector */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <DecisionCycleSelector
          cycles={cycles}
          currentCycle={currentCycle}
          onCycleChange={handleCycleChange}
          onCreateCycle={handleCreateCycle}
          onEditCycle={handleEditCycle}
          onDeleteCycle={handleDeleteCycle}
          loading={currentCycleLoading}
        />
      </Stack>
      
      {/* Pipeline Timeline */}
      {currentCycleLoading ? (
        <Box 
          sx={{ 
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center', 
            minHeight: 200 
          }}
        >
          <CircularProgress />
        </Box>
      ) : currentCycle ? (
        <DecisionCycleTimeline
          cycle={currentCycle}
          accountId={accountId}
          onStepClick={handleStepClick}
          onActivityClick={handleActivityClick}
          onAddActivity={handleAddActivity}
          onRefresh={mutateCycle}
          loading={currentCycleLoading}
        />
      ) : null}
      
      {/* Cycle Modal (Create/Edit) */}
      <DecisionCycleModal
        open={cycleModalOpen}
        onClose={handleCycleModalClose}
        cycle={cycleToEdit}
        accountId={accountId}
        onSuccess={handleCycleSuccess}
      />
      
      {/* Activity Modal (Create within step) */}
      <ActivityModal
        open={activityModalOpen}
        onClose={handleActivityModalClose}
        activity={null}
        accountId={accountId}
        decisionCycleId={currentCycleId}
        decisionStepId={activityTargetStep?.id}
        onSuccess={handleActivitySuccess}
      />
    </Box>
  );
}

DecisionCycleTab.propTypes = {
  accountId: PropTypes.string.isRequired,
  accountName: PropTypes.string
};