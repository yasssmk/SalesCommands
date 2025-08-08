import PropTypes from 'prop-types';
import { useMemo, useState, useEffect, useCallback } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';

// project-imports
import FormAccountAdd from './FormAccountAdd';
import MainCard from 'components/MainCard';
import SimpleBar from 'components/third-party/SimpleBar';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

import { useGetCustomer } from 'api/customer';

// ==============================|| CUSTOMER ADD / EDIT ||============================== //

export default function AccountModal({ open, modalToggler, accounts=[], onSuccess }) {
  // const { customersLoading: loading } = useGetCustomer();

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(false);
  }, []);

  const closeModal = useCallback(() => modalToggler(false), [modalToggler]);


  const accountForm = useMemo(
    () => !loading && <FormAccountAdd accounts={accounts} closeModal={closeModal}  onSuccess={onSuccess} />,
    // eslint-disable-next-line
    [accounts, loading]
  );

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={closeModal}
          aria-labelledby="modal-customer-add-label"
          aria-describedby="modal-customer-add-description"
          sx={{
            '& .MuiPaper-root:focus': {
              outline: 'none'
            }
          }}
        >
          <MainCard
            sx={{ width: `calc(100% - 48px)`, minWidth: 340, maxWidth: 880, height: 'auto', maxHeight: 'calc(100vh - 48px)' }}
            modal
            content={false}
          >
            <SimpleBar
              sx={{
                maxHeight: `calc(100vh - 48px)`,
                '& .simplebar-content': {
                  display: 'flex',
                  flexDirection: 'column'
                }
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
            </SimpleBar>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

AccountModal.propTypes = { open: PropTypes.bool, modalToggler: PropTypes.func, account: PropTypes.object, accounts: PropTypes.array, onSuccess: PropTypes.func };
