// frontend/src/sections/businessData/contacts/ContactModal.jsx

'use client';
import PropTypes from 'prop-types';
import { useMemo } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';

// project imports
import FormContactAdd from './FormContactAdd';
import FormContactEdit from './FormContactEdit';
import MainCard from 'components/MainCard';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

// api
import { useGetContacts } from 'api/businessData/contacts';

// ==============================|| CONTACT MODAL ||============================== //

/**
 * Contact Modal Component
 * 
 * Wrapper modal that displays either FormContactAdd or FormContactEdit
 * based on whether a contact is provided.
 * 
 * @param {boolean} open - Modal open state
 * @param {Function} modalToggler - Function to toggle modal state
 * @param {Object} contact - Contact object for edit mode (null for create)
 * @param {Object} prefilledAccount - Optional account to prefill in create mode
 */
export default function ContactModal({ open, modalToggler, contact, prefilledAccount = null }) {
  const { contactsLoading: loading } = useGetContacts();
  
  const closeModal = () => modalToggler(false);

  const contactForm = useMemo(() => {
    if (loading) return null;
    return contact && contact.id ? (
      <FormContactEdit contact={contact} contactId={contact.id} closeModal={closeModal} />
    ) : (
      <FormContactAdd closeModal={closeModal} prefilledAccount={prefilledAccount} />
    );
  }, [contact, loading, prefilledAccount]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={closeModal}
          aria-labelledby="modal-contact-add-label"
          aria-describedby="modal-contact-add-description"
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
                contactForm
              )}
            </Box>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

ContactModal.propTypes = {
  open: PropTypes.bool,
  modalToggler: PropTypes.func,
  contact: PropTypes.object,
  prefilledAccount: PropTypes.object
};