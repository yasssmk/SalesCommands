// frontend/src/sections/admin/users/FormUserAdd.jsx

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
import { useGetUserRoles, useGetOrganizations, useGetTeams, insertUser } from 'api/admin/users';

// project imports
import Avatar from 'components/@extended/Avatar';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';
import { openSnackbar } from 'api/snackbar';

// utils
import { isValidUUID } from 'utils/validators';

// assets
import CameraOutlined from '@ant-design/icons/CameraOutlined';

// ====== FORM VALUES ======
const buildInitialValues = () => ({
  email: '',
  first_name: '',
  last_name: '',
  password: '',
  is_active: true,
  is_superuser: false, 
  role: '',
  organization: '',
  team: ''
});

const CreateSchema = Yup.object().shape({
  // ✅ Email: trim whitespace + validate format
  email: Yup.string()
    .trim()
    .max(255)
    .required('Email is required')
    .email('Must be a valid email'),
  
  // ✅ Names: trim whitespace
  first_name: Yup.string().trim().max(50),
  last_name: Yup.string().trim().max(50),
  
  // ✅ Password: minimum 8 characters
  password: Yup.string()
    .min(8, 'Must be at least 8 characters')
    .required('Password is required'),
  
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
  ['email', 'first_name', 'last_name', 'is_active', 'is_superuser'].forEach((k) => {
    if (values[k] !== undefined && values[k] !== '') out[k] = values[k];
  });
  if (values.password) out.password = values.password;
  ['role', 'organization', 'team'].forEach((k) => {
    const v = values[k];
    if (v !== undefined && v !== '' && v !== null) out[k] = v;
  });
  return out;
}

// ==============================|| USER ADD - FORM (CREATE ONLY) ||============================== //
export default function FormUserAdd({ closeModal }) {
  const theme = useTheme();

  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(undefined);
  const [avatar, setAvatar] = useState(undefined);

  useEffect(() => {
    if (selectedImage) setAvatar(URL.createObjectURL(selectedImage));
  }, [selectedImage]);

  useEffect(() => {
    setLoading(false);
  }, []);

  const formik = useFormik({
    
    initialValues: buildInitialValues(),
    validationSchema: CreateSchema,
    enableReinitialize: false,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        const payload = sanitizePayload(values);
        const result = await insertUser(payload);

        if (result.success) {
          openSnackbar({
            open: true,
            message: 'User created successfully.',
            variant: 'alert',
            alert: { color: 'success' }
          });
          setSubmitting(false);
          closeModal?.();
        } else {
          openSnackbar({
            open: true,
            message: result.error || 'Failed to create user',
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

  // Fetch teams ONLY when an organization is selected
  const teamsEnabled = Boolean(values?.organization);
  const { teams = [], teamsLoading } = useGetTeams(
    teamsEnabled ? { organization: values.organization } : undefined,
    teamsEnabled
  );

  const filteredTeams = useMemo(() => Array.isArray(teams) ? teams : [], [teams]);

  // Auto-fill organization when team selected (if organization is empty)
  useEffect(() => {
    if (!values.team || !(teams?.length)) return;
    const t = (teams || []).find((x) => String(x.id) === String(values.team));
    const orgId = t?.organization?.id ?? t?.organization;
    if (orgId && !values.organization) setFieldValue('organization', String(orgId), false);
  }, [values.team, teams]); // eslint-disable-line react-hooks/exhaustive-deps

  const anyLoading = loading || rolesLoading || organizationsLoading || teamsLoading;

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
        <Form autoComplete="off" noValidate onSubmit={handleSubmit}  >
          <DialogTitle>New User</DialogTitle>
          <Divider />
          <DialogContent sx={{ p: 2.5}}>
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
                      <InputLabel htmlFor="user-password">Password</InputLabel>
                      <TextField
                        type="password"
                        fullWidth
                        id="user-password"
                        placeholder="At least 8 characters"
                        {...getFieldProps('password')}
                        error={Boolean(touched.password && errors.password)}
                        helperText={touched.password && errors.password}
                      />
                    </Stack>
                  </Grid>

                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-role">Role</InputLabel>
                      <FormControl fullWidth error={Boolean(touched.role && errors.role)}>
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
                        {touched.role && errors.role && (
                          <Typography variant="caption" color="error" sx={{ mt: 0.5, ml: 1.5 }}>
                            {errors.role}
                          </Typography>
                        )}
                      </FormControl>
                    </Stack>
                  </Grid>

                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-organization">Organization</InputLabel>
                      <FormControl fullWidth error={Boolean(touched.organization && errors.organization)}>
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
                                  No organization available
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
                              <Typography color="text.secondary">No organization available</Typography>
                            </MenuItem>
                          ) : (
                            (orgs || []).map((o) => (
                              <MenuItem key={o.id} value={String(o.id)}>
                                <ListItemText primary={o.name} />
                              </MenuItem>
                            ))
                          )}
                        </Select>
                        {touched.organization && errors.organization && (
                          <Typography variant="caption" color="error" sx={{ mt: 0.5, ml: 1.5 }}>
                            {errors.organization}
                          </Typography>
                          )}
                      </FormControl>
                    </Stack>
                  </Grid>

                  <Grid item xs={12}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-team">Team</InputLabel>
                      <FormControl fullWidth error={Boolean(touched.team && errors.team)}>
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
                                  No team available
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
                              <Typography color="text.secondary">No team available</Typography>
                            </MenuItem>
                          ) : (
                            filteredTeams.map((t) => (
                              <MenuItem key={t.id} value={String(t.id)}>
                                <ListItemText primary={t.name} />
                              </MenuItem>
                            ))
                          )}
                        </Select>
                        {touched.team && errors.team && (
                          <Typography variant="caption" color="error" sx={{ mt: 0.5, ml: 1.5 }}>
                            {errors.team}
                          </Typography>
                        )}
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
                  <Button type="submit" variant="contained" disabled={!formik.isValid || isSubmitting}>
                    Create
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
  closeModal: PropTypes.func
};
