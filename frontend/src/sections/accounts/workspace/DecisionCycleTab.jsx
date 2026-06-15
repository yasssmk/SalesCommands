// frontend/src/sections/accounts/workspace/DecisionCycleTab.jsx
/**
 * Decision Cycle Tab Component
 *
 * Main tab content for Decision Cycle (Pipeline) in Account Workspace.
 * Shows a filterable cards list of all cycles on the account.
 * Each card navigates to the full DC Workspace.
 *
 * Features:
 * - Cards list with Active / All / Won / Lost filters
 * - Empty state when no cycles
 * - Modal for create cycle
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';

// @ant-design/icons
import PlusOutlined from '@ant-design/icons/PlusOutlined';

// project imports
import DecisionCycleEmpty from '../decision-cycles/DecisionCycleEmpty';
import DecisionCycleModal from '../decision-cycles/DecisionCycleModal';
import DecisionCycleCardsList from '../dc-workspace/DecisionCycleCardsList';

import {
  useGetDecisionCyclesByAccount,
} from 'api/accounts/decisionCycles';

// ==============================|| DECISION CYCLE TAB ||============================== //

export default function DecisionCycleTab({ accountId, accountName }) {

  // Cycle Modal state (Create)
  const [cycleModalOpen, setCycleModalOpen] = useState(false);

  // ==============================|| DATA FETCHING ||============================== //

  const {
    cycles,
    cyclesLoading,
    mutateCycles
  } = useGetDecisionCyclesByAccount(accountId);

  // ==============================|| CYCLE HANDLERS ||============================== //

  const handleCreateCycle = useCallback(() => {
    setCycleModalOpen(true);
  }, []);

  const handleCycleModalClose = useCallback(() => {
    setCycleModalOpen(false);
  }, []);

  const handleCycleSuccess = useCallback(() => {
    mutateCycles();
  }, [mutateCycles]);

  // ==============================|| EMPTY STATE ||============================== //

  if (!cyclesLoading && (!cycles || cycles.length === 0)) {
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
      {/* Header with create button */}
      <Stack direction="row" justifyContent="flex-end" sx={{ mb: 2 }}>
        <Button
          variant="contained"
          size="small"
          startIcon={<PlusOutlined />}
          onClick={handleCreateCycle}
        >
          New Cycle
        </Button>
      </Stack>

      {/* Cards list */}
      <DecisionCycleCardsList
        accountId={accountId}
        cycles={cycles}
        cyclesLoading={cyclesLoading}
      />

      {/* Cycle Modal (Create) */}
      <DecisionCycleModal
        open={cycleModalOpen}
        onClose={handleCycleModalClose}
        cycle={null}
        accountId={accountId}
        onSuccess={handleCycleSuccess}
      />
    </Box>
  );
}

DecisionCycleTab.propTypes = {
  accountId: PropTypes.string.isRequired,
  accountName: PropTypes.string,
};
