import PropTypes from 'prop-types';
import useMediaQuery from '@mui/material/useMediaQuery';
import Grid from '@mui/material/Grid';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Link from '@mui/material/Link';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemSecondaryAction from '@mui/material/ListItemSecondaryAction';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import DialogContent from '@mui/material/DialogContent';
import Button from '@mui/material/Button';

// third-party
import { PatternFormat } from 'react-number-format';
import ToolOutlined from '@ant-design/icons/ToolOutlined';

// project import
import MainCard from 'components/MainCard';
import Avatar from 'components/@extended/Avatar';
import { displayInfoSnackbar } from 'utils/displayError';

// assets
import EnvironmentOutlined from '@ant-design/icons/EnvironmentOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import BankOutlined from '@ant-design/icons/BankOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';

// ==============================|| EXPANDING TABLE - USER DETAILS ||============================== //

export default function ExpandingUserDetail({ data }) {
  const downMD = useMediaQuery((theme) => theme.breakpoints.down('md'));

  const handlePlaceholderAction = () => {
    displayInfoSnackbar('User detail is under construction. Coming soon!');
  };

  return (
    <Grid container spacing={2.5} sx={{ pl: { xs: 0, sm: 5, md: 6, lg: 10, xl: 12 } }}>
      <DialogContent sx={{ p: 4 }}>
        <Stack spacing={3} alignItems="center" justifyContent="center" sx={{ minHeight: 300 }}>
          <ToolOutlined style={{ fontSize: '4rem', color: '#1976d2' }} />
          <Typography variant="h4" color="primary">
            In construction...
          </Typography>
          <Typography variant="body1" color="text.secondary" textAlign="center">
            User detail is under construction. 
            <br />
            Coming soon!
          </Typography>
          <Button 
            variant="outlined" 
            color="primary" 
            onClick={handlePlaceholderAction}
            sx={{ mt: 2 }}
          >
            Know more.
          </Button>
        </Stack>
      </DialogContent>
    </Grid>
  );
}

ExpandingUserDetail.propTypes = { data: PropTypes.any };

//   return (
//     <>
//       <FormikProvider value={formik}>
//         <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
//           <DialogTitle>{user ? 'Edit User' : 'New User'}</DialogTitle>
//           <Divider />
//           <DialogContent sx={{  p: 2.5 }}>
//             <Grid container spacing={3}>
//               <Grid item xs={12} md={3}>
//                 <Stack direction="row" justifyContent="center" sx={{ mt: 3 }}>
//                   <FormLabel
//                     htmlFor="change-avtar"
//                     sx={{
//                       position: 'relative',
//                       borderRadius: '50%',
//                       overflow: 'hidden',
//                       '&:hover .MuiBox-root': { opacity: 1 },
//                       cursor: 'pointer'
//                     }}
//                   >
//                     <Avatar alt="Avatar 1" src={avatar} sx={{ width: 72, height: 72, border: '1px dashed' }} />
//                     <Box
//                       sx={{
//                         position: 'absolute',
//                         top: 0,
//                         left: 0,
//                         background: 'rgba(0,0,0,.65)',
//                         width: '100%',
//                         height: '100%',
//                         opacity: 0,
//                         display: 'flex',
//                         alignItems: 'center',
//                         justifyContent: 'center'
//                       }}
//                     >
//                       <Stack spacing={0.5} alignItems="center">
//                         <CameraOutlined style={{ color: 'white', fontSize: '2rem' }} />
//                         <Typography sx={{ color: 'white' }}>Upload</Typography>
//                       </Stack>
//                     </Box>
//                   </FormLabel>
//                   <TextField
//                     type="file"
//                     id="change-avtar"
//                     placeholder="Outlined"
//                     variant="outlined"
//                     sx={{ display: 'none' }}
//                     onChange={(e) => setSelectedImage(e.target.files?.[0])}
//                   />
//                 </Stack>
//               </Grid>
//               <Grid item xs={12} md={9}>
//                 <Grid container spacing={3}>
//                   <Grid item xs={12} sm={6}>
//                     <Stack spacing={1.25}>
//                       <InputLabel htmlFor="user-firstname">First Name</InputLabel>
//                       <TextField
//                         fullWidth
//                         id="user-firstname"
//                         placeholder="Enter First Name"
//                         {...getFieldProps('first_name')}
//                         error={Boolean(touched.first_name && errors.first_name)}
//                         helperText={touched.first_name && errors.first_name}
//                       />
//                     </Stack>
//                   </Grid>
//                   <Grid item xs={12} sm={6}>
//                     <Stack spacing={1.25}>
//                       <InputLabel htmlFor="user-lastname">Last Name</InputLabel>
//                       <TextField
//                         fullWidth
//                         id="user-lastname"
//                         placeholder="Enter Last Name"
//                         {...getFieldProps('last_name')}
//                         error={Boolean(touched.last_name && errors.last_name)}
//                         helperText={touched.last_name && errors.last_name}
//                       />
//                     </Stack>
//                   </Grid>
//                   <Grid item xs={12} sm={6}>
//                     <Stack spacing={1.25}>
//                       <InputLabel htmlFor="user-email">Email</InputLabel>
//                       <TextField
//                         fullWidth
//                         id="user-email"
//                         placeholder="Enter Email Address"
//                         {...getFieldProps('email')}
//                         error={Boolean(touched.email && errors.email)}
//                         helperText={touched.email && errors.email}
//                       />
//                     </Stack>
//                   </Grid>
//                   <Grid item xs={12} sm={6}>
//                     <Stack spacing={1.25}>
//                       <InputLabel htmlFor="user-role">Role</InputLabel>
//                       <FormControl fullWidth error={Boolean(touched.role_name && errors.role_name)}>
//                         <Select
//                           id="user-role"
//                           displayEmpty
//                           {...getFieldProps('role_name')}
//                           onChange={(event) => setFieldValue('role_name', event.target.value)}
//                         >
//                           <MenuItem disabled value="">
//                             <em>Select Role</em>
//                           </MenuItem>
//                           {allRoles.map((role) => (
//                             <MenuItem key={role.value} value={role.value}>
//                               {role.label}
//                             </MenuItem>
//                           ))}
//                         </Select>
//                         {touched.role_name && errors.role_name && (
//                           <FormHelperText error id="standard-weight-helper-text-role">
//                             {errors.role_name}
//                           </FormHelperText>
//                         )}
//                       </FormControl>
//                     </Stack>
//                   </Grid>
//                   <Grid item xs={12} sm={6}>
//                     <Stack spacing={1.25}>
//                       <InputLabel htmlFor="user-organization">Organization</InputLabel>
//                       <FormControl fullWidth>
//                         <Select
//                           id="user-organization"
//                           displayEmpty
//                           value={getFieldProps('organization').value?.id || ''}
//                           onChange={(event) => {
//                             const selectedOrg = allOrganizations.find(org => org.id === event.target.value);
//                             setFieldValue('organization', selectedOrg || null);
//                           }}
//                         >
//                           <MenuItem value="">
//                             <em>Select Organization</em>
//                           </MenuItem>
//                           {allOrganizations.map((org) => (
//                             <MenuItem key={org.id} value={org.id}>
//                               {org.name}
//                             </MenuItem>
//                           ))}
//                         </Select>
//                       </FormControl>
//                     </Stack>
//                   </Grid>
//                   <Grid item xs={12} sm={6}>
//                     <Stack spacing={1.25}>
//                       <InputLabel htmlFor="user-team">Team</InputLabel>
//                       <FormControl fullWidth>
//                         <Select
//                           id="user-team"
//                           displayEmpty
//                           value={getFieldProps('team').value?.id || ''}
//                           onChange={(event) => {
//                             const selectedTeam = allTeams.find(team => team.id === event.target.value);
//                             setFieldValue('team', selectedTeam || null);
//                           }}
//                         >
//                           <MenuItem value="">
//                             <em>Select Team</em>
//                           </MenuItem>
//                           {allTeams.map((team) => (
//                             <MenuItem key={team.id} value={team.id}>
//                               {team.name}
//                             </MenuItem>
//                           ))}
//                         </Select>
//                       </FormControl>
//                     </Stack>
//                   </Grid>
//                   <Grid item xs={12} sm={6}>
//                     <Stack spacing={1.25}>
//                       <Typography variant="subtitle1">Account Status</Typography>
//                       <FormControlLabel
//                         control={
//                           <Switch
//                             checked={getFieldProps('is_active').value}
//                             onChange={(event) => setFieldValue('is_active', event.target.checked)}
//                             name="is_active"
//                           />
//                         }
//                         label={getFieldProps('is_active').value ? 'Active' : 'Inactive'}
//                       />
//                     </Stack>
//                   </Grid>
//                   <Grid item xs={12} sm={6}>
//                     <Stack spacing={1.25}>
//                       <Typography variant="subtitle1">Staff Access</Typography>
//                       <FormControlLabel
//                         control={
//                           <Switch
//                             checked={getFieldProps('is_staff').value}
//                             onChange={(event) => setFieldValue('is_staff', event.target.checked)}
//                             name="is_staff"
//                           />
//                         }
//                         label={getFieldProps('is_staff').value ? 'Staff Member' : 'Regular User'}
//                       />
//                     </Stack>
//                   </Grid>
//                 </Grid>
//               </Grid>
//             </Grid>
//           </DialogContent>
//           <Divider />
//           <DialogActions sx={{ p: 2.5 }}>
//             <Grid container justifyContent="space-between" alignItems="center">
//               <Grid item>
//                 {user && (
//                   <Tooltip title="Delete User" placement="top">
//                     <IconButton onClick={() => setOpenAlert(true)} size="large" color="error">
//                       <DeleteFilled />
//                     </IconButton>
//                   </Tooltip>
//                 )}
//               </Grid>
//               <Grid item>
//                 <Stack direction="row" spacing={2} alignItems="center">
//                   <Button color="error" onClick={closeModal}>
//                     Cancel
//                   </Button>
//                   <Button type="submit" variant="contained" disabled={isSubmitting}>
//                     {user ? 'Edit' : 'Add'}
//                   </Button>
//                 </Stack>
//               </Grid>
//             </Grid>
//           </DialogActions>
//         </Form>
//       </FormikProvider>
//       {user && <AlertUserDelete id={user.id} title={`${user.first_name} ${user.last_name}`} open={openAlert} handleClose={handleAlertClose} />}
//     </>
//   );
// }

// FormUserAdd.propTypes = { 
//   user: PropTypes.any, 
//   closeModal: PropTypes.func 
// };