// frontend/src/sections/accounts/workspace/DecisionCycleTab.jsx
/**
 * Decision Cycle Tab Component
 * 
 * Main tab content for Decision Cycle in Account Workspace.
 * Orchestrates all decision cycle components.
 * 
 * Features:
 * - Cycle selector at top
 * - Timeline display for current cycle
 * - Empty state when no cycles
 * - Modals for create/edit cycle and steps
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback, useMemo } from 'react';

// material-ui
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';

// project imports
import DecisionCycleSelector from '../decision-cycles/DecisionCycleSelector';
import DecisionCycleTimeline from '../decision-cycles/DecisionCycleTimeline';
import DecisionCycleEmpty from '../decision-cycles/DecisionCycleEmpty';
import DecisionCycleModal from '../decision-cycles/DecisionCycleModal';
import DecisionStepModal from '../decision-cycles/DecisionStepModal';
import DecisionStepDetail from '../decision-cycles/DecisionStepDetail';
import AlertStepDelete from '../decision-cycles/AlertStepDelete';

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
  
  // ==============================|| STATE ||============================== //
  
  // Selected cycle ID
  const [selectedCycleId, setSelectedCycleId] = useState(null);
  
  // Modals state
  const [cycleModalOpen, setCycleModalOpen] = useState(false);
  const [cycleToEdit, setCycleToEdit] = useState(null);
  
  const [stepModalOpen, setStepModalOpen] = useState(false);
  const [stepToEdit, setStepToEdit] = useState(null);
  const [defaultStage, setDefaultStage] = useState(null);
  
  const [stepDetailOpen, setStepDetailOpen] = useState(false);
  const [stepDetail, setStepDetail] = useState(null);
  
  const [deleteStepOpen, setDeleteStepOpen] = useState(false);
  const [stepToDelete, setStepToDelete] = useState(null);
  
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
  
  // Fetch current cycle details with steps
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
    if (!window.confirm(`Are you sure you want to delete "${cycle.name}"? This will also delete all steps.`)) {
      return;
    }
    
    try {
      const result = await deleteDecisionCycle(cycle.id);
      
      if (result.success) {
        displaySuccessSnackbar('Decision cycle deleted successfully');
        
        // Clear selection if deleted cycle was selected
        if (selectedCycleId === cycle.id) {
          setSelectedCycleId(null);
        }
        
        // Revalidate cycles list
        mutateCycles();
      } else {
        displayErrorSnackbar(result.error || 'Failed to delete cycle');
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'An error occurred');
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
  
  // ==============================|| STEP HANDLERS ||============================== //
  
  const handleAddStep = useCallback((stage) => {
    setStepToEdit(null);
    setDefaultStage(stage);
    setStepModalOpen(true);
  }, []);
  
  const handleEditStep = useCallback((step) => {
    // Open detail view instead of edit modal
    setStepDetail(step);
    setStepDetailOpen(true);
  }, []);
  
  const handleStepModalClose = useCallback(() => {
    setStepModalOpen(false);
    setStepToEdit(null);
    setDefaultStage(null);
  }, []);
  
  const handleStepDetailClose = useCallback(() => {
    setStepDetailOpen(false);
    setStepDetail(null);
  }, []);
  
  const handleStepSuccess = useCallback(() => {
    mutateCycle();
  }, [mutateCycle]);
  
  const handleStepUpdate = useCallback((updatedStep) => {
    // Update local step detail
    setStepDetail(updatedStep);
    // Revalidate cycle to refresh timeline
    mutateCycle();
  }, [mutateCycle]);
  
  const handleStepDeleteRequest = useCallback((step) => {
    setStepToDelete(step);
    setDeleteStepOpen(true);
    // Close detail modal
    setStepDetailOpen(false);
    setStepDetail(null);
  }, []);
  
  const handleStepDeleteClose = useCallback(() => {
    setDeleteStepOpen(false);
    setStepToDelete(null);
  }, []);
  
  const handleStepDeleteSuccess = useCallback(() => {
    mutateCycle();
  }, [mutateCycle]);
  
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
      
      {/* Timeline */}
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
          onAddStep={handleAddStep}
          onEditStep={handleEditStep}
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
      
      {/* Step Modal (Create) */}
      <DecisionStepModal
        open={stepModalOpen}
        modalToggler={setStepModalOpen}
        step={null}
        cycleId={currentCycleId}
        defaultStage={defaultStage}
        onSuccess={handleStepSuccess}
      />
      
      {/* Step Detail Modal */}
      {stepDetailOpen && stepDetail && (
        <Box
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            bgcolor: 'rgba(0, 0, 0, 0.5)',
            zIndex: 1300,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
          onClick={handleStepDetailClose}
        >
          <Box
            onClick={(e) => e.stopPropagation()}
            sx={{
              width: 'calc(100% - 48px)',
              maxWidth: 680,
              maxHeight: 'calc(100vh - 48px)',
              bgcolor: 'background.paper',
              borderRadius: 2,
              boxShadow: 24,
              overflow: 'hidden'
            }}
          >
            <Box
              sx={{
                maxHeight: 'calc(100vh - 48px)',
                overflowY: 'auto'
              }}
            >
              <DecisionStepDetail
                step={stepDetail}
                closeModal={handleStepDetailClose}
                onUpdate={handleStepUpdate}
                onDelete={handleStepDeleteRequest}
              />
            </Box>
          </Box>
        </Box>
      )}
      
      {/* Delete Step Alert */}
      <AlertStepDelete
        open={deleteStepOpen}
        onClose={handleStepDeleteClose}
        step={stepToDelete}
        cycleId={currentCycleId}
        onSuccess={handleStepDeleteSuccess}
      />
    </Box>
  );
}

DecisionCycleTab.propTypes = {
  accountId: PropTypes.string.isRequired,
  accountName: PropTypes.string
};