// import PropTypes from 'prop-types';
// import { useMemo } from 'react';

// // material-ui
// import Box from '@mui/material/Box';
// import Modal from '@mui/material/Modal';
// import Stack from '@mui/material/Stack';

// // project-imports
// import FormUserAdd from './FormUserAdd';
// import MainCard from 'components/MainCard';
// import SimpleBar from 'components/third-party/SimpleBar';
// import CircularWithPath from 'components/@extended/progress/CircularWithPath';

// import { useGetUsers } from 'api/admin/users';

// // ==============================|| USER ADD / EDIT ||============================== //

// export default function UserModal({ open, modalToggler, user }) {
//   const { usersLoading: loading } = useGetUsers();

//   const closeModal = () => modalToggler(false);

//   const userForm = useMemo(
//     () => !loading && <FormUserAdd user={user || null} closeModal={closeModal} />,
//     // eslint-disable-next-line
//     [user, loading]
//   );

//   return (
//     <>
//       {open && (
//         <Modal
//           open={open}
//           onClose={closeModal}
//           aria-labelledby="modal-user-add-label"
//           aria-describedby="modal-user-add-description"
//           sx={{
//             '& .MuiPaper-root:focus': {
//               outline: 'none',
//             }
//           }}
//         >
//           <MainCard
//             sx={{ width: `calc(100% - 48px)`, minWidth: 340, maxWidth: 880, height: 'auto', maxHeight: 'calc(100vh - 48px)' }}
//             modal
//             content={false}
//           >
//             <SimpleBar
//               sx={{
//                 maxHeight: `calc(100vh - 48px)`,
//                 '& .simplebar-content': {
//                   display: 'flex',
//                   flexDirection: 'column'
//                 }
//               }}
//             >
//               {loading ? (
//                 <Box sx={{ p: 5 }}>
//                   <Stack direction="row" justifyContent="center">
//                     <CircularWithPath />
//                   </Stack>
//                 </Box>
//               ) : (
//                 userForm
//               )}
//             </SimpleBar>
//           </MainCard>
//         </Modal>
//       )}
//     </>
//   );
// }

// UserModal.propTypes = { 
//   open: PropTypes.bool, 
//   modalToggler: PropTypes.func, 
//   user: PropTypes.any 
// };

import PropTypes from 'prop-types';
import { useMemo } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Modal from '@mui/material/Modal';
import Stack from '@mui/material/Stack';

// project-imports
import FormUserAdd from './FormUserAdd';
import FormUserEdit from './FormUserEdit';
import MainCard from 'components/MainCard';
import SimpleBar from 'components/third-party/SimpleBar';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

import { useGetUsers } from 'api/admin/users';

// ==============================|| USER ADD / EDIT ||============================== //

export default function UserModal({ open, modalToggler, user }) {
  const { usersLoading: loading } = useGetUsers();

  const closeModal = () => modalToggler(false);

  const userForm = useMemo(() => {
    if (loading) return null;
    return user && user.id ? (
      <FormUserEdit user={user} userId={user.id} closeModal={closeModal} />
    ) : (
      <FormUserAdd closeModal={closeModal} />
    );
  }, [user, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={closeModal}
          aria-labelledby="modal-user-add-label"
          aria-describedby="modal-user-add-description"
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
                userForm
              )}
            </SimpleBar>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

UserModal.propTypes = {
  open: PropTypes.bool,
  modalToggler: PropTypes.func,
  user: PropTypes.any
};