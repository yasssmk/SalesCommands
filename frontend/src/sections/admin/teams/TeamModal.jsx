// frontend/src/sections/admin/teams/TeamModal.jsx

'use client';
import PropTypes from 'prop-types';
import { useMemo } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';

// project-imports
import FormTeamAdd from './FormTeamAdd';
import MainCard from 'components/MainCard';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

// ============================================
// 🔴 FINAL VERSION (API ready) - COMMENTED FOR NOW
// ============================================
// import { useGetTeams } from 'api/admin/teams';
//
// export default function TeamModal({ open, modalToggler, team }) {
//   const { teamsLoading: loading } = useGetTeams();
//   const closeModal = () => modalToggler(false);
//
//   const teamForm = useMemo(() => {
//     if (loading) return null;
//     return team && team.id ? (
//       <FormTeamEdit team={team} teamId={team.id} closeModal={closeModal} />
//     ) : (
//       <FormTeamAdd closeModal={closeModal} />
//     );
//   }, [team, loading]); // eslint-disable-line react-hooks/exhaustive-deps
//
//   return (
//     <>
//       {open && (
//         <Modal
//           open={open}
//           onClose={closeModal}
//           aria-labelledby="modal-team-add-label"
//           aria-describedby="modal-team-add-description"
//           sx={{
//             '& .MuiPaper-root:focus': { outline: 'none' }
//           }}
//         >
//           <MainCard
//             sx={{
//               width: `calc(100% - 48px)`,
//               minWidth: 340,
//               maxWidth: 880,
//               height: 'auto',
//               maxHeight: 'calc(100vh - 48px)'
//             }}
//             modal
//             content={false}
//           >
//             <Box
//               sx={{
//                 maxHeight: 'calc(100vh - 48px)',
//                 overflowY: 'auto',
//                 WebkitOverflowScrolling: 'touch',
//                 overscrollBehavior: 'contain',
//                 '& > :last-child': { marginBottom: 0, paddingBottom: 0 }
//               }}
//             >
//               {loading ? (
//                 <Box sx={{ p: 5 }}>
//                   <Stack direction="row" justifyContent="center">
//                     <CircularWithPath />
//                   </Stack>
//                 </Box>
//               ) : (
//                 teamForm
//               )}
//             </Box>
//           </MainCard>
//         </Modal>
//       )}
//     </>
//   );
// }

// ============================================
// 🟡 TEMPORARY VERSION (UX only) - TO DELETE WHEN API READY
// ============================================
export default function TeamModal({ open, modalToggler, team }) {
  // TODO: Replace with real API call when backend ready
  const loading = false;
  
  const closeModal = () => modalToggler(false);

  const teamForm = useMemo(() => {
    if (loading) return null;
    return team && team.id ? (
      <FormTeamEdit team={team} teamId={team.id} closeModal={closeModal} />
    ) : (
      <FormTeamAdd closeModal={closeModal} />
    );
  }, [team, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={closeModal}
          aria-labelledby="modal-team-add-label"
          aria-describedby="modal-team-add-description"
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
            {/* Native scroll container (same pattern as UserModal/RoleModal) */}
            <Box
              sx={{
                maxHeight: 'calc(100vh - 48px)',
                overflowY: 'auto',
                // iOS: smooth scrolling
                WebkitOverflowScrolling: 'touch',
                // Prevent overscroll bounce creating double scrollbars
                overscrollBehavior: 'contain',
                // Remove bottom margin from last form element
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
                teamForm
              )}
            </Box>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

TeamModal.propTypes = {
  open: PropTypes.bool,
  modalToggler: PropTypes.func,
  team: PropTypes.any
};