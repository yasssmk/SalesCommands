// frontend/src/sections/territories/TerritoryModal.jsx

'use client';
import PropTypes from 'prop-types';
import { useMemo } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';

// project-imports
import FormTerritoryAdd from './FormTerritoryAdd';
import FormTerritoryEdit from './FormTerritoryEdit';
import MainCard from 'components/MainCard';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

// api
import { useGetTerritories } from 'api/territories/territories';

// ==============================|| TERRITORY MODAL ||============================== //

export default function TerritoryModal({ open, closeModal, territory, initialFilters = {} }) {
  const { territoriesLoading: loading } = useGetTerritories({ page: 1, pageSize: 1 });

  const territoryForm = useMemo(() => {
  if (loading) return null;
  return territory && territory.id ? (
    <FormTerritoryEdit territory={territory} closeModal={closeModal} />
  ) : (
    <FormTerritoryAdd closeModal={closeModal} initialFilters={initialFilters} />
  );
}, [territory, loading, closeModal, initialFilters]);

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={closeModal}
          aria-labelledby="modal-territory-add-label"
          aria-describedby="modal-territory-add-description"
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
            {/* Native scroll container (same pattern as UserModal) */}
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
                territoryForm
              )}
            </Box>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

TerritoryModal.propTypes = {
  open: PropTypes.bool.isRequired,
  closeModal: PropTypes.func.isRequired,
  territory: PropTypes.object,
  initialFilters: PropTypes.object
};