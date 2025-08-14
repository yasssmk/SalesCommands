import PropTypes from 'prop-types';
import { useEffect, useState } from 'react';

// material-ui
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormLabel from '@mui/material/FormLabel';
import Grid from '@mui/material/Grid';
import FormHelperText from '@mui/material/FormHelperText';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import OutlinedInput from '@mui/material/OutlinedInput';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// third-party
import _ from 'lodash';
import * as Yup from 'yup';
import { useFormik, Form, FormikProvider } from 'formik';

// project imports
import AlertUserDelete from './AlertUserDelete';
import Avatar from 'components/@extended/Avatar';
import IconButton from 'components/@extended/IconButton';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';

import { openSnackbar } from 'api/snackbar';
import { insertUser, updateUser } from 'api/admin/users';

// assets
import CameraOutlined from '@ant-design/icons/CameraOutlined';
import DeleteFilled from '@ant-design/icons/DeleteFilled';

// constant
const getInitialValues = (user) => {
  const newUser = {
    first_name: '',
    last_name: '',
    email: '',
    role_name: '',
    organization: null,
    team: null,
    is_active: true,
    is_staff: false,
    avatar: 1
  };

  if (user) {
    return _.merge({}, newUser, user);
  }

  return newUser;
};

const allRoles = [
  { value: 'Admin', label: 'Admin' },
  { value: 'Manager', label: 'Manager' },
  { value: 'User', label: 'User' },
  { value: 'Viewer', label: 'Viewer' }
];

// Mock data for organizations and teams - will be replaced with API calls
const allOrganizations = [
  { id: 1, name: 'Sales Department' },
  { id: 2, name: 'Marketing Department' },
  { id: 3, name: 'Engineering Department' },
  { id: 4, name: 'HR Department' }
];

const allTeams = [
  { id: 1, name: 'Sales Team A' },
  { id: 2, name: 'Marketing Team B' },
  { id: 3, name: 'Dev Team Alpha' },
  { id: 4, name: 'Dev Team Beta' }
];

// ==============================|| USER ADD / EDIT - FORM ||============================== //

export default function FormUserAdd({ user, closeModal }) {
  const theme = useTheme();

  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(undefined);
  const [avatar, setAvatar] = useState(
    `/assets/images/users/avatar-${user && user !== null && user?.avatar ? user.avatar : 1}.png`
  );

  useEffect(() => {
    if (selectedImage) {
      setAvatar(URL.createObjectURL(selectedImage));
    }
  }, [selectedImage]);

  useEffect(() => {
    setLoading(false);
  }, []);

  const UserSchema = Yup.object().shape({
    first_name: Yup.string().max(50).required('First Name is required'),
    last_name: Yup.string().max(50).required('Last Name is required'),
    email: Yup.string().max(255).required('Email is required').email('Must be a valid email'),
    role_name: Yup.string().required('Role is required')
  });

  const [openAlert, setOpenAlert] = useState(false);

  const handleAlertClose = () => {
    setOpenAlert(!openAlert);
    closeModal();
  };

  const formik = useFormik({
    initialValues: getInitialValues(user),
    validationSchema: UserSchema,
    enableReinitialize: true,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        let newUser = values;

        if (user) {
          updateUser(newUser.id, newUser).then(() => {
            openSnackbar({
              open: true,
              message: 'User updated successfully.',
              variant: 'alert',
              alert: {
                color: 'success'
              }
            });
            setSubmitting(false);
            closeModal();
          });
        } else {
          await insertUser(newUser).then(() => {
            openSnackbar({
              open: true,
              message: 'User added successfully.',
              variant: 'alert',
              alert: {
                color: 'success'
              }
            });
            setSubmitting(false);
            closeModal();
          });
        }
      } catch (error) {
        console.error(error);
        openSnackbar({
          open: true,
          message: 'An error occurred. Please try again.',
          variant: 'alert',
          alert: {
            color: 'error'
          }
        });
        setSubmitting(false);
      }
    }
  });

  const { errors, touched, handleSubmit, isSubmitting, getFieldProps, setFieldValue } = formik;

  if (loading)
    return (
      <Box sx={{ p: 5 }}>
        <Stack direction="row" justifyContent="center">
          <CircularWithPath />
        </Stack>
      </Box>
    );

  return (
    <>
      <FormikProvider value={formik}>
        <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
          <DialogTitle>{user ? 'Edit User' : 'New User'}</DialogTitle>
          <Divider />
          <DialogContent sx={{ p: 2.5 }}>
            <Grid container spacing={3}>
              <Grid item xs={12} md={3}>
                <Stack direction="row" justifyContent="center" sx={{ mt: 3 }}>
                  <FormLabel
                    htmlFor="change-avtar"
                    sx={{
                      position: 'relative',
                      borderRadius: '50%',
                      overflow: 'hidden',
                      '&:hover .MuiBox-root': { opacity: 1 },
                      cursor: 'pointer'
                    }}
                  >
                    <Avatar alt="Avatar 1" src={avatar} sx={{ width: 72, height: 72, border: '1px dashed' }} />
                    <Box
                      sx={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        background: 'rgba(0,0,0,.65)',
                        width: '100%',
                        height: '100%',
                        opacity: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                    >
                      <Stack spacing={0.5} alignItems="center">
                        <CameraOutlined style={{ color: 'white', fontSize: '2rem' }} />
                        <Typography sx={{ color: 'white' }}>Upload</Typography>
                      </Stack>
                    </Box>
                  </FormLabel>
                  <TextField
                    type="file"
                    id="change-avtar"
                    placeholder="Outlined"
                    variant="outlined"
                    sx={{ display: 'none' }}
                    onChange={(e) => setSelectedImage(e.target.files?.[0])}
                  />
                </Stack>
              </Grid>
              <Grid item xs={12} md={9}>
                <Grid container spacing={3}>
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1.25}>
                      <InputLabel htmlFor="user-firstname">First Name</InputLabel>
                      <TextField
                        fullWidth
                        id="user-firstname"
                        placeholder="Enter First Name"
                        {...getFieldProps('first_name')}
                        error={Boolean(touched.first_name && errors.first_name)}
                        helperText={touched.first_name && errors.first_name}
                      />
                    </Stack>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1.25}>
                      <InputLabel htmlFor="user-lastname">Last Name</InputLabel>
                      <TextField
                        fullWidth
                        id="user-lastname"
                        placeholder="Enter Last Name"
                        {...getFieldProps('last_name')}
                        error={Boolean(touched.last_name && errors.last_name)}
                        helperText={touched.last_name && errors.last_name}
                      />
                    </Stack>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1.25}>
                      <InputLabel htmlFor="user-email">Email</InputLabel>
                      <TextField
                        fullWidth
                        id="user-email"
                        placeholder="Enter Email Address"
                        {...getFieldProps('email')}
                        error={Boolean(touched.email && errors.email)}
                        helperText={touched.email && errors.email}
                      />
                    </Stack>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1.25}>
                      <InputLabel htmlFor="user-role">Role</InputLabel>
                      <FormControl fullWidth error={Boolean(touched.role_name && errors.role_name)}>
                        <Select
                          id="user-role"
                          displayEmpty
                          {...getFieldProps('role_name')}
                          onChange={(event) => setFieldValue('role_name', event.target.value)}
                        >
                          <MenuItem disabled value="">
                            <em>Select Role</em>
                          </MenuItem>
                          {allRoles.map((role) => (
                            <MenuItem key={role.value} value={role.value}>
                              {role.label}
                            </MenuItem>
                          ))}
                        </Select>
                        {touched.role_name && errors.role_name && (
                          <FormHelperText error id="standard-weight-helper-text-role">
                            {errors.role_name}
                          </FormHelperText>
                        )}
                      </FormControl>
                    </Stack>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1.25}>
                      <InputLabel htmlFor="user-organization">Organization</InputLabel>
                      <FormControl fullWidth>
                        <Select
                          id="user-organization"
                          displayEmpty
                          value={getFieldProps('organization').value?.id || ''}
                          onChange={(event) => {
                            const selectedOrg = allOrganizations.find(org => org.id === event.target.value);
                            setFieldValue('organization', selectedOrg || null);
                          }}
                        >
                          <MenuItem value="">
                            <em>Select Organization</em>
                          </MenuItem>
                          {allOrganizations.map((org) => (
                            <MenuItem key={org.id} value={org.id}>
                              {org.name}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Stack>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1.25}>
                      <InputLabel htmlFor="user-team">Team</InputLabel>
                      <FormControl fullWidth>
                        <Select
                          id="user-team"
                          displayEmpty
                          value={getFieldProps('team').value?.id || ''}
                          onChange={(event) => {
                            const selectedTeam = allTeams.find(team => team.id === event.target.value);
                            setFieldValue('team', selectedTeam || null);
                          }}
                        >
                          <MenuItem value="">
                            <em>Select Team</em>
                          </MenuItem>
                          {allTeams.map((team) => (
                            <MenuItem key={team.id} value={team.id}>
                              {team.name}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Stack>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1.25}>
                      <Typography variant="subtitle1">Account Status</Typography>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={getFieldProps('is_active').value}
                            onChange={(event) => setFieldValue('is_active', event.target.checked)}
                            name="is_active"
                          />
                        }
                        label={getFieldProps('is_active').value ? 'Active' : 'Inactive'}
                      />
                    </Stack>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1.25}>
                      <Typography variant="subtitle1">Staff Access</Typography>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={getFieldProps('is_staff').value}
                            onChange={(event) => setFieldValue('is_staff', event.target.checked)}
                            name="is_staff"
                          />
                        }
                        label={getFieldProps('is_staff').value ? 'Staff Member' : 'Regular User'}
                      />
                    </Stack>
                  </Grid>
                </Grid>
              </Grid>
            </Grid>
          </DialogContent>
          <Divider />
          <DialogActions sx={{ p: 2.5 }}>
            <Grid container justifyContent="space-between" alignItems="center">
              <Grid item>
                {user && (
                  <Tooltip title="Delete User" placement="top">
                    <IconButton onClick={() => setOpenAlert(true)} size="large" color="error">
                      <DeleteFilled />
                    </IconButton>
                  </Tooltip>
                )}
              </Grid>
              <Grid item>
                <Stack direction="row" spacing={2} alignItems="center">
                  <Button color="error" onClick={closeModal}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="contained" disabled={isSubmitting}>
                    {user ? 'Edit' : 'Add'}
                  </Button>
                </Stack>
              </Grid>
            </Grid>
          </DialogActions>
        </Form>
      </FormikProvider>
      {user && <AlertUserDelete id={user.id} title={`${user.first_name} ${user.last_name}`} open={openAlert} handleClose={handleAlertClose} />}
    </>
  );
}

FormUserAdd.propTypes = { 
  user: PropTypes.any, 
  closeModal: PropTypes.func 
};