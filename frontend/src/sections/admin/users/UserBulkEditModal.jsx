// frontend/src/sections/admin/users/UserBulkEditModal.jsx

'use client';
import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';

// project imports
import FormUserBulkEdit from './FormUserBulkEdit';
import MainCard from 'components/MainCard';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

export default function UserBulkEditModal({ open, modalToggler, selectedUserIds = [], selectedCount = 0 }) {
  const closeModal = () => modalToggler(false);

  // Validation : au moins 1 user sélectionné
  if (selectedCount === 0 || selectedUserIds.length === 0) {
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
            {/* Conteneur scroll natif (même style que UserModal) */}
            <Box
              sx={{
                maxHeight: 'calc(100vh - 48px)',
                overflowY: 'auto',
                WebkitOverflowScrolling: 'touch',
                overscrollBehavior: 'contain',
                '& > :last-child': { marginBottom: 0, paddingBottom: 0 }
              }}
            >
              <FormUserBulkEdit 
                closeModal={closeModal} 
                selectedUserIds={selectedUserIds}
                selectedCount={selectedCount}
              />
            </Box>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

UserBulkEditModal.propTypes = {
  open: PropTypes.bool.isRequired,
  modalToggler: PropTypes.func.isRequired,
  selectedUserIds: PropTypes.array.isRequired,
  selectedCount: PropTypes.number.isRequired
};