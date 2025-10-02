// frontend/src/sections/admin/users/FormUserEdit.jsx

import PropTypes from 'prop-types';
import React, { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

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
import InputLabel from '@mui/material/InputLabel';
import Link from '@mui/material/Link';
import ListItemText from '@mui/material/ListItemText';
import MenuItem from '@mui/material/MenuItem';
import OutlinedInput from '@mui/material/OutlinedInput';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// third-party
import * as Yup from 'yup';
import { useFormik, Form, FormikProvider } from 'formik';

// api hooks
import { useGetUser, useGetUserRoles, useGetOrganizations, useGetTeams, updateUser } from 'api/admin/users';

// project imports
import Avatar from 'components/@extended/Avatar';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';
import { openSnackbar } from 'api/snackbar';

// utils
import { isValidUUID } from 'utils/validators';

// assets
import CameraOutlined from '@ant-design/icons/CameraOutlined';

// ====== FORM VALUES ======
const buildInitialValues = (user) => ({
  email: user?.email || '',
  first_name: user?.first_name || '',
  last_name: user?.last_name || '',
  is_active: user?.is_active ?? true,
  is_superuser: user?.is_superuser ?? false,
  role: user?.role ? String(user.role) : '',
  organization: user?.organization ? String(user.organization) : '',
  team: user?.team ? String(user.team) : ''
});

const EditSchema = Yup.object().shape({
  // ✅ Email: Keep validation for consistency, but field is disabled (read-only)
  email: Yup.string()
    .max(255)
    .required('Email is required')
    .email('Must be a valid email'),
  
  // ✅ Names: trim whitespace
  first_name: Yup.string().trim().max(50),
  last_name: Yup.string().trim().max(50),
  
  // ✅ UUID fields: validate UUID format when value is provided
  role: Yup.string()
    .nullable()
    .test('is-valid-uuid', 'Invalid role selection', function(value) {
      // Allow empty/null (optional field)
      if (!value || value === '') return true;
      // Validate UUID format
      return isValidUUID(value);
    }),
  
  organization: Yup.string()
    .nullable()
    .test('is-valid-uuid', 'Invalid organization selection', function(value) {
      // Allow empty/null (optional field)
      if (!value || value === '') return true;
      // Validate UUID format
      return isValidUUID(value);
    }),
  
  team: Yup.string()
    .nullable()
    .test('is-valid-uuid', 'Invalid team selection', function(value) {
      // Allow empty/null (optional field)
      if (!value || value === '') return true;
      // Validate UUID format
      return isValidUUID(value);
    })
});

function sanitizePayload(values) {
  const out = {};
  // do NOT include email (read-only)
  ['first_name', 'last_name', 'is_active', 'is_superuser'].forEach((k) => {
    if (values[k] !== undefined && values[k] !== '') out[k] = values[k];
  });
  ['role', 'organization', 'team'].forEach((k) => {
    const v = values[k];
    if (v !== undefined && v !== '' && v !== null) out[k] = v;
  });
  return out;
}

// ==============================|| USER EDIT - FORM ||============================== //
function FormUserEdit({ closeModal, userId, user: initialUser, onChangePassword }) {
  const theme = useTheme();

  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(undefined);
  const [avatar, setAvatar] = useState(undefined);

  const { user: fetchedUser, userLoading } = useGetUser(userId);
  const userData = initialUser || fetchedUser;

  const router = useRouter();

  useEffect(() => {
    if (selectedImage) setAvatar(URL.createObjectURL(selectedImage));
  }, [selectedImage]);

  useEffect(() => {
    setLoading(false);
  }, []);

  const formik = useFormik({
    initialValues: buildInitialValues(userData),
    validationSchema: EditSchema,
    enableReinitialize: true,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        const payload = sanitizePayload(values);
        const result = await updateUser(userData.id, payload);

        if (result.success) {
          openSnackbar({
            open: true,
            message: 'User updated successfully.',
            variant: 'alert',
            alert: { color: 'success' }
          });
          setSubmitting(false);
          closeModal?.();
        } else {
          openSnackbar({
            open: true,
            message: result.error || 'Failed to update user',
            variant: 'alert',
            alert: { color: 'error' }
          });
          setSubmitting(false);
        }
      } catch (err) {
        openSnackbar({
          open: true,
          message: err?.message || 'Unexpected error',
          variant: 'alert',
          alert: { color: 'error' }
        });
        setSubmitting(false);
      }
    }
  });

  const { errors, touched, handleSubmit, isSubmitting, getFieldProps, setFieldValue, values } = formik;

  const { roles = [], rolesLoading } = useGetUserRoles();
  const { organizations: orgs = [], organizationsLoading } = useGetOrganizations();

  const teamsEnabled = Boolean(values?.organization);
  const { teams = [], teamsLoading } = useGetTeams(
    teamsEnabled ? { organization: values.organization } : undefined,
    teamsEnabled
  );

  const filteredTeams = useMemo(() => (Array.isArray(teams) ? teams : []), [teams]);

  useEffect(() => {
    if (!values.team || !(teams?.length)) return;
    const t = (teams || []).find((x) => String(x.id) === String(values.team));
    const orgId = t?.organization?.id ?? t?.organization;
    if (orgId && !values.organization) setFieldValue('organization', String(orgId), false);
  }, [values.team, teams]); // eslint-disable-line react-hooks/exhaustive-deps

  const anyLoading = loading || userLoading || rolesLoading || organizationsLoading || teamsLoading;

  if (anyLoading || !userData)
    return (
      <Box sx={{ p: 5 }}>
        <Stack direction="row" justifyContent="center">
          <CircularWithPath />
        </Stack>
      </Box>
    );

  const noOrgOrTeam = (orgs?.length ?? 0) === 0 && (teams?.length ?? 0) === 0;
  const noTeamsToShow = (filteredTeams?.length ?? 0) === 0;

  return (
    <>
      <FormikProvider value={formik}>
        <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
          <DialogTitle>Edit User</DialogTitle>
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
                    <Avatar alt="Avatar" src={avatar} sx={{ width: 72, height: 72, border: '1px dashed' }} />
                    <Box
                      sx={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        background: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, .75)' : 'rgba(0,0,0,.65)',
                        width: '100%',
                        height: '100%',
                        opacity: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                    >
                      <Stack spacing={0.5} alignItems="center">
                        <CameraOutlined style={{ fontSize: '2rem' }} />
                        <Typography sx={{ color: 'secondary.lighter' }}>Upload</Typography>
                      </Stack>
                    </Box>
                  </FormLabel>
                  <TextField
                    type="file"
                    id="change-avtar"
                    variant="outlined"
                    sx={{ display: 'none' }}
                    onChange={(e) => setSelectedImage(e.target.files?.[0])}
                  />
                </Stack>
              </Grid>

              <Grid item xs={12} md={8}>
                <Grid container spacing={3}>
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-firstName">First name</InputLabel>
                      <TextField
                        fullWidth
                        id="user-firstName"
                        placeholder="First name"
                        {...getFieldProps('first_name')}
                        error={Boolean(touched.first_name && errors.first_name)}
                        helperText={touched.first_name && errors.first_name}
                      />
                    </Stack>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-lastName">Last name</InputLabel>
                      <TextField
                        fullWidth
                        id="user-lastName"
                        placeholder="Last name"
                        {...getFieldProps('last_name')}
                        error={Boolean(touched.last_name && errors.last_name)}
                        helperText={touched.last_name && errors.last_name}
                      />
                    </Stack>
                  </Grid>

                  <Grid item xs={12}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-email">Email</InputLabel>
                      <TextField
                        fullWidth
                        id="user-email"
                        placeholder="name@company.com"
                        {...getFieldProps('email')}
                        disabled
                        error={Boolean(touched.email && errors.email)}
                        helperText={touched.email && errors.email}
                      />
                    </Stack>
                  </Grid>

                  {/* no password field here */}

                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-role">Role</InputLabel>
                      <FormControl fullWidth>
                        <Select
                          id="user-role"
                          displayEmpty
                          value={values.role}
                          onChange={(e) => setFieldValue('role', e.target.value)}
                          input={<OutlinedInput id="select-user-role" placeholder="Select role" />}
                          renderValue={(selected) => {
                            if ((roles?.length ?? 0) === 0) {
                              return (
                                <Typography variant="subtitle1" color="text.secondary">
                                  No roles available
                                </Typography>
                              );
                            }
                            if (!selected) return <Typography variant="subtitle1">Select role</Typography>;
                            const r = roles?.find((x) => String(x.id) === String(selected));
                            return <Typography variant="subtitle2">{r?.name || '—'}</Typography>;
                          }}
                        >
                          {(roles || []).length === 0 ? (
                            <MenuItem disabled>
                              <Typography color="text.secondary">No roles available</Typography>
                            </MenuItem>
                          ) : (
                            (roles || []).map((r) => (
                              <MenuItem key={r.id} value={String(r.id)}>
                                <ListItemText primary={r.name} />
                              </MenuItem>
                            ))
                          )}
                        </Select>
                      </FormControl>
                    </Stack>
                  </Grid>

                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-organization">Organization</InputLabel>
                      <FormControl fullWidth>
                        <Select
                          id="user-organization"
                          displayEmpty
                          value={values.organization}
                          onChange={(e) => setFieldValue('organization', e.target.value)}
                          input={<OutlinedInput id="select-user-org" placeholder="Select organization" />}
                          renderValue={(selected) => {
                            if ((orgs?.length ?? 0) === 0) {
                              return (
                                <Typography variant="subtitle1" color="text.secondary">
                                  No team or organization available
                                </Typography>
                              );
                            }
                            if (!selected) return <Typography variant="subtitle1">Select organization</Typography>;
                            const o = orgs?.find((x) => String(x.id) === String(selected));
                            return <Typography variant="subtitle2">{o?.name || '—'}</Typography>;
                          }}
                        >
                          {(orgs || []).length === 0 ? (
                            <MenuItem disabled>
                              <Typography color="text.secondary">No team or organization available</Typography>
                            </MenuItem>
                          ) : (
                            (orgs || []).map((o) => (
                              <MenuItem key={o.id} value={String(o.id)}>
                                <ListItemText primary={o.name} />
                              </MenuItem>
                            ))
                          )}
                        </Select>
                      </FormControl>
                    </Stack>
                  </Grid>

                  <Grid item xs={12}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-team">Team</InputLabel>
                      <FormControl fullWidth>
                        <Select
                          id="user-team"
                          displayEmpty
                          value={values.team}
                          onChange={(e) => setFieldValue('team', e.target.value)}
                          input={<OutlinedInput id="select-user-team" placeholder="Select team" />}
                          renderValue={(selected) => {
                            if (noOrgOrTeam || noTeamsToShow) {
                              return (
                                <Typography variant="subtitle1" color="text.secondary">
                                  No team or organization available
                                </Typography>
                              );
                            }
                            if (!selected) return <Typography variant="subtitle1">Select team</Typography>;
                            const t = filteredTeams.find((x) => String(x.id) === String(selected));
                            return <Typography variant="subtitle2">{t?.name || '—'}</Typography>;
                          }}
                        >
                          {noOrgOrTeam || noTeamsToShow ? (
                            <MenuItem disabled>
                              <Typography color="text.secondary">No team or organization available</Typography>
                            </MenuItem>
                          ) : (
                            filteredTeams.map((t) => (
                              <MenuItem key={t.id} value={String(t.id)}>
                                <ListItemText primary={t.name} />
                              </MenuItem>
                            ))
                          )}
                        </Select>
                      </FormControl>
                    </Stack>
                  </Grid>

                  <Grid item xs={12}>
                      <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                        <Stack spacing={0.5}>
                          <Typography variant="subtitle1">Active account</Typography>
                          <Typography variant="caption" color="text.secondary">
                            Allows this user to sign in
                          </Typography>
                        </Stack>
                        <Switch 
                        checked={values.is_active} 
                        onChange={(e) => setFieldValue('is_active', e.target.checked)} 
                        sx={{ mt: 0 }} 
                      />
                      </Stack>
                  </Grid>
                  
                  <Grid item xs={12}>
                    <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                      <Stack spacing={0.5}>
                        <Typography variant="subtitle1">SuperUser</Typography>
                        <Typography variant="caption" color="text.secondary">
                          Give admin rights to user
                        </Typography>
                      </Stack>
                      <Switch 
                        checked={values.is_superuser} 
                        onChange={(e) => setFieldValue('is_superuser', e.target.checked)} 
                        sx={{ mt: 0 }} 
                      />
                    </Stack>
                  </Grid>

                  <Grid item xs={12}>
                    <Stack spacing={1}>
                        <Link
                        variant="caption"
                        color="primary"
                        fontWeight= '600'
                        fontSize= '0.875rem'
                        onClick={() => router.push(`/users/${String(userData?.id)}/change-password`)}
                        sx={{ cursor: 'pointer', mt: 1, alignSelf: 'flex-start' }}
                          // href={`/users/${String(userData?.id)}/change-password`}
                        underline="hover"
                        >
                          Change user password
                        </Link>
                    </Stack>
                  </Grid>
                </Grid>
              </Grid>
            </Grid>
          </DialogContent>
          <Divider />
          <DialogActions sx={{ p: 2.5 }}>
            <Grid container justifyContent="space-between" alignItems="center">
              <Grid item />
              <Grid item>
                <Stack direction="row" spacing={2} alignItems="center">
                  <Button color="error" onClick={closeModal}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="contained" disabled={!formik.isValid || isSubmitting} >
                    Save
                  </Button>
                </Stack>
              </Grid>
            </Grid>
          </DialogActions>
        </Form>
      </FormikProvider>
    </>
  );
}

FormUserEdit.propTypes = {
  closeModal: PropTypes.func,
  userId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  user: PropTypes.object,
  onChangePassword: PropTypes.func
};

export default React.memo(FormUserEdit)
