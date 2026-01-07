// frontend/src/sections/accounts/decision-cycles/DecisionStepModal.jsx
/**
 * Decision Step Modal Component
 * 
 * Modal for creating new decision steps.
 * Edit is handled via DecisionStepDetail (inline editing).
 */

'use client';

import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Modal from '@mui/material/Modal';

// project imports
import MainCard from 'components/MainCard';
import FormStepAdd from './FormStepAdd';

// ==============================|| DECISION STEP MODAL ||============================== //

/**
 * Decision Step Modal Component
 * 
 * @param {boolean} open - Modal open state
 * @param {Function} modalToggler - Function to toggle modal state
 * @param {string} cycleId - Parent cycle UUID (required)
 * @param {string} defaultStage - Default stage for new step
 * @param {Function} onSuccess - Callback after successful save
 */
export default function DecisionStepModal({ 
  open, 
  modalToggler, 
  cycleId,
  defaultStage = null,
  onSuccess
}) {
  
  const closeModal = () => {
    modalToggler(false);
  };
  
  const handleSuccess = (data) => {
    onSuccess?.(data);
    closeModal();
  };

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={closeModal}
          aria-labelledby="modal-step-label"
          aria-describedby="modal-step-description"
          sx={{
            '& .MuiPaper-root:focus': { outline: 'none' }
          }}
        >
          <MainCard
            sx={{
              width: `calc(100% - 48px)`,
              minWidth: 340,
              maxWidth: 680,
              height: 'auto',
              maxHeight: 'calc(100vh - 48px)',
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)'
            }}
            modal
            content={false}
          >
            <Box
              sx={{
                maxHeight: 'calc(100vh - 48px)',
                overflowY: 'auto',
                WebkitOverflowScrolling: 'touch',
                overscrollBehavior: 'contain',
                '& > :last-child': { marginBottom: 0, paddingBottom: 0 }
              }}
            >
              <FormStepAdd 
                cycleId={cycleId}
                defaultStage={defaultStage}
                closeModal={closeModal} 
                onSuccess={handleSuccess}
              />
            </Box>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

DecisionStepModal.propTypes = {
  open: PropTypes.bool.isRequired,
  modalToggler: PropTypes.func.isRequired,
  cycleId: PropTypes.string,
  defaultStage: PropTypes.string,
  onSuccess: PropTypes.func
};