import PropTypes from 'prop-types';
import { useEffect, useMemo, useState } from 'react';

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
import { useGetUser, useGetUserRoles, useGetOrganizations, useGetTeams, insertUser, updateUser } from 'api/admin/users';

// project imports
import Avatar from 'components/@extended/Avatar';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';
import { openSnackbar } from 'api/snackbar';

// assets
import CameraOutlined from '@ant-design/icons/CameraOutlined';

// ====== FORM VALUES ======
const buildInitialValues = (user) => ({
  email: user?.email || '',
  first_name: user?.first_name || '',
  last_name: user?.last_name || '',
  password: '', // write-only; blank keeps current on edit
  is_active: user?.is_active ?? true,
  role: user?.role ? String(user.role) : '',
  organization: user?.organization ? String(user.organization) : '',
  team: user?.team ? String(user.team) : ''
});

const CreateSchema = Yup.object().shape({
  email: Yup.string().max(255).required('Email is required').email('Must be a valid email'),
  first_name: Yup.string().max(50),
  last_name: Yup.string().max(50),
  password: Yup.string().min(8, 'Must be at least 8 characters').required('Password is required'),
  role: Yup.mixed().nullable(),
  organization: Yup.mixed().nullable(),
  team: Yup.mixed().nullable()
});

const EditSchema = Yup.object().shape({
  email: Yup.string().max(255).required('Email is required').email('Must be a valid email'),
  first_name: Yup.string().max(50),
  last_name: Yup.string().max(50),
  // Optional on edit; if provided, must be >= 8
  password: Yup.string().test('len', 'Must be at least 8 characters', (v) => !v || v.length >= 8),
  role: Yup.mixed().nullable(),
  organization: Yup.mixed().nullable(),
  team: Yup.mixed().nullable()
});

function sanitizePayload(values) {
  const out = {};
  // primitives
  ['email', 'first_name', 'last_name', 'is_active'].forEach((k) => {
    if (values[k] !== undefined && values[k] !== '') out[k] = values[k];
  });
  // password only if provided
  if (values.password) out.password = values.password;
  // relations (ids kept as-is: could be UUID strings)
  ['role', 'organization', 'team'].forEach((k) => {
    const v = values[k];
    if (v !== undefined && v !== '' && v !== null) out[k] = v;
  });
  return out;
}

// ==============================|| USER ADD / EDIT - FORM (API CONNECTED) ||============================== //
export default function FormUserAdd({ closeModal, userId, user: initialUser }) {
  const theme = useTheme();

  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(undefined);
  const [avatar, setAvatar] = useState(undefined);

  // Load existing user if editing
  const { user: fetchedUser, userLoading } = useGetUser(userId);
  const userData = initialUser || fetchedUser;
  const isEdit = Boolean(userData && userData.id);

  useEffect(() => {
    if (selectedImage) {
      setAvatar(URL.createObjectURL(selectedImage));
    }
  }, [selectedImage]);

  // initial skeleton spinner only
  useEffect(() => {
    setLoading(false);
  }, []);

  const formik = useFormik({
    initialValues: buildInitialValues(userData),
    validationSchema: isEdit ? EditSchema : CreateSchema,
    enableReinitialize: true,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        const payload = sanitizePayload(values);
        let result;
        if (isEdit) {
          result = await updateUser(userData.id, payload); // uses PUT in your API helper
        } else {
          result = await insertUser(payload);
        }

        if (result.success) {
          openSnackbar({
            open: true,
            message: isEdit ? 'User updated successfully.' : 'User created successfully.',
            variant: 'alert',
            alert: { color: 'success' }
          });
          setSubmitting(false);
          closeModal?.();
        } else {
          openSnackbar({
            open: true,
            message: result.error || (isEdit ? 'Failed to update user' : 'Failed to create user'),
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

  // --- Lists from backend (scoped by tenant via axiosClient/api) ---
  const { roles = [], rolesLoading } = useGetUserRoles();
  const { organizations: orgs = [], organizationsLoading } = useGetOrganizations();

  // Fetch teams ONLY when an organization is selected to avoid backend 400s
  const teamsEnabled = Boolean(values?.organization);
  const { teams = [], teamsLoading } = useGetTeams(
    teamsEnabled ? { organization: values.organization } : undefined,
    teamsEnabled
  );

  const filteredTeams = useMemo(() => {
    // Backend already filters by organization when enabled; keep a safe fallback
    const base = Array.isArray(teams) ? teams : [];
    return base;
  }, [teams]);

  // Auto-fill organization when team selected (if organization is empty)
  useEffect(() => {
    if (!values.team || !(teams?.length)) return;
    const t = (teams || []).find((x) => String(x.id) === String(values.team));
    const orgId = t?.organization?.id ?? t?.organization;
    if (orgId && !values.organization) setFieldValue('organization', String(orgId), false);
  }, [values.team, teams]);

  const anyLoading = loading || userLoading || rolesLoading || organizationsLoading || teamsLoading;

  if (anyLoading)
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
          <DialogTitle>{isEdit ? 'Edit User' : 'New User'}</DialogTitle>
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
                    placeholder="Outlined"
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
                        error={Boolean(touched.email && errors.email)}
                        helperText={touched.email && errors.email}
                      />
                    </Stack>
                  </Grid>
                  <Grid item xs={12}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-password">{isEdit ? 'Password (optional)' : 'Password'}</InputLabel>
                      <TextField
                        type="password"
                        fullWidth
                        id="user-password"
                        placeholder={isEdit ? 'Leave blank to keep current password' : 'At least 8 characters'}
                        {...getFieldProps('password')}
                        error={Boolean(touched.password && errors.password)}
                        helperText={touched.password && errors.password}
                      />
                    </Stack>
                  </Grid>

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
                      <FormControlLabel
                        control={<Switch checked={values.is_active} onChange={(e) => setFieldValue('is_active', e.target.checked)} sx={{ mt: 0 }} />}
                        label=""
                        labelPlacement="start"
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
              <Grid item>{/* creation/edit only */}</Grid>
              <Grid item>
                <Stack direction="row" spacing={2} alignItems="center">
                  <Button color="error" onClick={closeModal}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="contained" disabled={isSubmitting}>
                    {isEdit ? 'Save' : 'Create'}
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

FormUserAdd.propTypes = {
  closeModal: PropTypes.func,
  userId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  user: PropTypes.object
};
