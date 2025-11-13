// 

'use client';
import PropTypes from 'prop-types';
import { useMemo } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';

// project-imports
import FormRoleAdd from './FormRoleAdd';
import FormRoleEdit from './FormRoleEdit';
import MainCard from 'components/MainCard';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

import { useGetRoles } from 'api/admin/roles';

export default function RoleModal({ open, modalToggler, role }) {
  const { rolesLoading: loading } = useGetRoles() ;

  const closeModal = () => modalToggler(false);

  const roleForm = useMemo(() => {
    if (loading) return null;
    return role && role.id ? (
      <FormRoleEdit role={role} roleId={role.id} closeModal={closeModal} />
    ) : (
      <FormRoleAdd closeModal={closeModal} />
    );
  }, [role, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={closeModal}
          aria-labelledby="modal-customer-add-label"
          aria-describedby="modal-customer-add-description"
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
            {/* Conteneur scroll natif (remplace SimpleBar) */}
            <Box
              sx={{
                maxHeight: 'calc(100vh - 48px)',
                overflowY: 'auto',
                // iOS: inertie du scroll
                WebkitOverflowScrolling: 'touch',
                // évite les “rebonds” qui créent des doubles scrollbars
                overscrollBehavior: 'contain',
                // si le dernier élément du formulaire a une grosse marge basse
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
                roleForm
              )}
            </Box>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

RoleModal.propTypes = {
  open: PropTypes.bool,
  modalToggler: PropTypes.func,
  role: PropTypes.any
};
