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

// project imports (réutilise tes composants existants)
import Avatar from 'components/@extended/Avatar';
import CircularWithPath from 'components/@extended/progress/CircularWithPath';
import { openSnackbar } from 'api/snackbar';

// assets
import CameraOutlined from '@ant-design/icons/CameraOutlined';

// ==============================|| DUMMY DATA (rendu uniquement) ||============================== //
const DUMMY_ROLES = [
  { id: 1, name: 'Sales Rep' },
  { id: 2, name: 'Manager' },
  { id: 3, name: 'Admin' }
];

const DUMMY_ORGS = [
  { id: 1, name: 'Sales' },
  { id: 2, name: 'Marketing' },
  { id: 3, name: 'Operations' }
];

const DUMMY_TEAMS = [
  { id: 1, name: 'Sales Team A', organization: 1 },
  { id: 2, name: 'Sales Team B', organization: 1 },
  { id: 3, name: 'Growth', organization: 2 },
  { id: 4, name: 'Field Ops', organization: 3 }
];

// ====== FORM VALUES ======
const getInitialValues = () => ({
  email: '',
  first_name: '',
  last_name: '',
  password: '', // write-only à la création
  is_active: true,
  role: '', // id
  organization: '', // id
  team: '' // id
});

const UserSchema = Yup.object().shape({
  email: Yup.string().max(255).required('Email requis').email('Email invalide'),
  first_name: Yup.string().max(50),
  last_name: Yup.string().max(50),
  password: Yup.string().min(8, 'Au moins 8 caractères').required('Mot de passe requis'),
  role: Yup.mixed().nullable(),
  organization: Yup.mixed().nullable(),
  team: Yup.mixed().nullable()
});

// ==============================|| USER ADD - FORM (RENDU UNIQUEMENT) ||============================== //
export default function FormUserAdd({ closeModal }) {
  const theme = useTheme();

  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(undefined);
  const [avatar, setAvatar] = useState('/assets/images/users/avatar-1.png');

  useEffect(() => {
    if (selectedImage) {
      setAvatar(URL.createObjectURL(selectedImage));
    }
  }, [selectedImage]);

  useEffect(() => {
    // rendu uniquement : pas d'appels réseau
    setLoading(false);
  }, []);

  const formik = useFormik({
    initialValues: getInitialValues(),
    validationSchema: UserSchema,
    enableReinitialize: false,
    onSubmit: async (values, { setSubmitting, resetForm }) => {
      // Rendu uniquement : aucune requête. On affiche juste un snackbar et on logue.
      // eslint-disable-next-line no-console
      console.log('[FormUserAdd] Preview submit values:', values);
      openSnackbar({
        open: true,
        message: "Mode aperçu : aucun envoi au backend.",
        variant: 'alert',
        alert: { color: 'info' }
      });
      setSubmitting(false);
      // Laisse le formulaire rempli pour démo; si tu veux reset :
      // resetForm();
      closeModal?.();
    }
  });

  const { errors, touched, handleSubmit, isSubmitting, getFieldProps, setFieldValue, values } = formik;

  const filteredTeams = useMemo(() => {
    const orgId = values.organization ? Number(values.organization) : null;
    return orgId ? DUMMY_TEAMS.filter((t) => t.organization === orgId) : DUMMY_TEAMS;
  }, [values.organization]);

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
          <DialogTitle>Nouvel utilisateur</DialogTitle>
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
                      <InputLabel htmlFor="user-firstName">Prénom</InputLabel>
                      <TextField
                        fullWidth
                        id="user-firstName"
                        placeholder="Prénom"
                        {...getFieldProps('first_name')}
                        error={Boolean(touched.first_name && errors.first_name)}
                        helperText={touched.first_name && errors.first_name}
                      />
                    </Stack>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-lastName">Nom</InputLabel>
                      <TextField
                        fullWidth
                        id="user-lastName"
                        placeholder="Nom"
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
                        placeholder="email@domaine.com"
                        {...getFieldProps('email')}
                        error={Boolean(touched.email && errors.email)}
                        helperText={touched.email && errors.email}
                      />
                    </Stack>
                  </Grid>
                  <Grid item xs={12}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-password">Mot de passe</InputLabel>
                      <TextField
                        type="password"
                        fullWidth
                        id="user-password"
                        placeholder="Au moins 8 caractères"
                        {...getFieldProps('password')}
                        error={Boolean(touched.password && errors.password)}
                        helperText={touched.password && errors.password}
                      />
                    </Stack>
                  </Grid>

                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-role">Rôle</InputLabel>
                      <FormControl fullWidth>
                        <Select
                          id="user-role"
                          displayEmpty
                          value={values.role}
                          onChange={(e) => setFieldValue('role', e.target.value)}
                          input={<OutlinedInput id="select-user-role" placeholder="Sélectionner un rôle" />}
                          renderValue={(selected) => {
                            if (!selected) return <Typography variant="subtitle1">Sélectionner un rôle</Typography>;
                            const r = DUMMY_ROLES.find((x) => String(x.id) === String(selected));
                            return <Typography variant="subtitle2">{r?.name || '—'}</Typography>;
                          }}
                        >
                          {DUMMY_ROLES.map((r) => (
                            <MenuItem key={r.id} value={String(r.id)}>
                              <ListItemText primary={r.name} />
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Stack>
                  </Grid>

                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-organization">Organisation</InputLabel>
                      <FormControl fullWidth>
                        <Select
                          id="user-organization"
                          displayEmpty
                          value={values.organization}
                          onChange={(e) => setFieldValue('organization', e.target.value)}
                          input={<OutlinedInput id="select-user-org" placeholder="Sélectionner une organisation" />}
                          renderValue={(selected) => {
                            if (!selected) return <Typography variant="subtitle1">Sélectionner une organisation</Typography>;
                            const o = DUMMY_ORGS.find((x) => String(x.id) === String(selected));
                            return <Typography variant="subtitle2">{o?.name || '—'}</Typography>;
                          }}
                        >
                          {DUMMY_ORGS.map((o) => (
                            <MenuItem key={o.id} value={String(o.id)}>
                              <ListItemText primary={o.name} />
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Stack>
                  </Grid>

                  <Grid item xs={12}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="user-team">Équipe</InputLabel>
                      <FormControl fullWidth>
                        <Select
                          id="user-team"
                          displayEmpty
                          value={values.team}
                          onChange={(e) => setFieldValue('team', e.target.value)}
                          input={<OutlinedInput id="select-user-team" placeholder="Sélectionner une équipe" />}
                          renderValue={(selected) => {
                            if (!selected) return <Typography variant="subtitle1">Sélectionner une équipe</Typography>;
                            const t = filteredTeams.find((x) => String(x.id) === String(selected));
                            return <Typography variant="subtitle2">{t?.name || '—'}</Typography>;
                          }}
                        >
                          {filteredTeams.map((t) => (
                            <MenuItem key={t.id} value={String(t.id)}>
                              <ListItemText primary={t.name} />
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Stack>
                  </Grid>

                  <Grid item xs={12}>
                    <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                      <Stack spacing={0.5}>
                        <Typography variant="subtitle1">Compte actif</Typography>
                        <Typography variant="caption" color="text.secondary">
                          Autorise la connexion de cet utilisateur
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
              <Grid item>{/* Pas de suppression ici : page dédiée à la création */}</Grid>
              <Grid item>
                <Stack direction="row" spacing={2} alignItems="center">
                  <Button color="error" onClick={closeModal}>
                    Annuler
                  </Button>
                  <Button type="submit" variant="contained" disabled={isSubmitting}>
                    Créer
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
