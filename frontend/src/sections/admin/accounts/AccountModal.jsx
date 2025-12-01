// frontend/src/sections/admin/accounts/AccountModal.jsx

'use client';
import PropTypes from 'prop-types';
import { useMemo } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';

// project imports
import FormAccountAdd from './FormAccountAdd';
import FormAccountEdit from './FormAccountEdit';
import MainCard from 'components/MainCard';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

// api
import { useGetAccounts } from 'api/admin/accounts';

// ==============================|| ACCOUNT MODAL ||============================== //

/**
 * Account Modal Component
 * 
 * Wrapper modal that displays either FormAccountAdd or FormAccountEdit
 * based on whether an account is provided.
 * 
 * @param {boolean} open - Modal open state
 * @param {Function} modalToggler - Function to toggle modal state
 * @param {Object} account - Account object for edit mode (null for create)
 */
export default function AccountModal({ open, modalToggler, account }) {
  const { accountsLoading: loading } = useGetAccounts();
  
  const closeModal = () => modalToggler(false);

  const accountForm = useMemo(() => {
    if (loading) return null;
    return account && account.id ? (
      <FormAccountEdit account={account} accountId={account.id} closeModal={closeModal} />
    ) : (
      <FormAccountAdd closeModal={closeModal} />
    );
  }, [account, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={closeModal}
          aria-labelledby="modal-account-add-label"
          aria-describedby="modal-account-add-description"
          sx={{
            '& .MuiPaper-root:focus': { outline: 'none' }
          }}
        >
          <MainCard
            sx={{
              width: `calc(100% - 48px)`,
              minWidth: 340,
              maxWidth: 880,
              height: 'auto',
              maxHeight: 'calc(100vh - 48px)'
            }}
            modal
            content={false}
          >
            {/* Native scroll container */}
            <Box
              sx={{
                maxHeight: 'calc(100vh - 48px)',
                overflowY: 'auto',
                WebkitOverflowScrolling: 'touch',
                overscrollBehavior: 'contain',
                '& > :last-child': { marginBottom: 0, paddingBottom: 0 }
              }}
            >
              {loading ? (
                <Box sx={{ p: 5 }}>
                  <Stack direction="row" justifyContent="center">
                    <CircularWithPath />
                  </Stack>
                </Box>
              ) : (
                accountForm
              )}
            </Box>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

AccountModal.propTypes = {
  open: PropTypes.bool,
  modalToggler: PropTypes.func,
  account: PropTypes.object
};