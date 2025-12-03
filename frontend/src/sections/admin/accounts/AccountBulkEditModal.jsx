// frontend/src/sections/admin/accounts/AccountBulkEditModal.jsx

'use client';
import PropTypes from 'prop-types';
import { useCallback } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';

// project imports
import FormAccountBulkEdit from './FormAccountBulkEdit';
import MainCard from 'components/MainCard';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

export default function AccountBulkEditModal({ open, modalToggler, selectedAccountIds = [], selectedCount = 0 }) {
  const closeModal = useCallback(() => {
    modalToggler(false);
  }, [modalToggler]);

  // Validation: at least 1 account selected
  if (selectedCount === 0 || selectedAccountIds.length === 0) {
    return null;
  }

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={closeModal}
          aria-labelledby="modal-bulk-edit-label"
          aria-describedby="modal-bulk-edit-description"
          sx={{
            '& .MuiPaper-root:focus': { outline: 'none' }
          }}
        >
          <MainCard
            sx={{
              width: `calc(100% - 48px)`,
              minWidth: 340,
              maxWidth: 720,
              height: 'auto',
              maxHeight: 'calc(100vh - 48px)'
            }}
            modal
            content={false}
          >
            {/* Native scroll container (same style as AccountModal) */}
            <Box
              sx={{
                maxHeight: 'calc(100vh - 48px)',
                overflowY: 'auto',
                WebkitOverflowScrolling: 'touch',
                overscrollBehavior: 'contain',
                '& > :last-child': { marginBottom: 0, paddingBottom: 0 }
              }}
            >
              <FormAccountBulkEdit 
                closeModal={closeModal} 
                selectedAccountIds={selectedAccountIds}
                selectedCount={selectedCount}
              />
            </Box>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

AccountBulkEditModal.propTypes = {
  open: PropTypes.bool.isRequired,
  modalToggler: PropTypes.func.isRequired,
  selectedAccountIds: PropTypes.array.isRequired,
  selectedCount: PropTypes.number.isRequired
};