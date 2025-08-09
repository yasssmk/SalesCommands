'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';

// material-ui
import useMediaQuery from '@mui/material/useMediaQuery';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid';
import InputAdornment from '@mui/material/InputAdornment';
import InputLabel from '@mui/material/InputLabel';
import OutlinedInput from '@mui/material/OutlinedInput';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';

// third party
import * as Yup from 'yup';
import { Formik } from 'formik';

// project import
import IconButton from 'components/@extended/IconButton';
import AnimateButton from 'components/@extended/AnimateButton';

// api
import { loginUser, storeTokens } from 'api/auth';

// assets
import EyeOutlined from '@ant-design/icons/EyeOutlined';
import EyeInvisibleOutlined from '@ant-design/icons/EyeInvisibleOutlined';

// ==============================|| DJANGO AUTH - LOGIN ||============================== //

export default function AuthLogin() {
  const router = useRouter();
  const downSM = useMediaQuery((theme) => theme.breakpoints.down('sm'));
  
  const [checked, setChecked] = useState(false);
  const [capsWarning, setCapsWarning] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleClickShowPassword = () => {
    setShowPassword(!showPassword);
  };

  const handleMouseDownPassword = (event) => {
    event.preventDefault();
  };

  const onKeyDown = (keyEvent) => {
    if (keyEvent.getModifierState('CapsLock')) {
      setCapsWarning(true);
    } else {
      setCapsWarning(false);
    }
  };

  return (
    <>
      <Formik
        initialValues={{
          email: '',
          password: '',
          submit: null
        }}
        validationSchema={Yup.object().shape({
          email: Yup.string()
            .email('Adresse email invalide')
            .max(255)
            .required('L\'email est requis'),
          password: Yup.string()
            .required('Le mot de passe est requis')
            .test(
              'no-leading-trailing-whitespace', 
              'Le mot de passe ne peut pas commencer ou finir par des espaces', 
              (value) => value === value?.trim()
            )
            .min(6, 'Le mot de passe doit contenir au moins 6 caractères')
        })}
        onSubmit={async (values, { setErrors, setSubmitting, setFieldError }) => {
          try {
            setSubmitting(true);
            
            // Appel API Django via le service séparé
            const response = await loginUser(values.email, values.password);
            
            // Stockage des tokens via le helper
            if (response.access_token || response.token) {
              storeTokens(
                response.access_token || response.token,
                response.refresh_token
              );
            }
            
            // Redirection vers le dashboard
            router.push('/');
            
          } catch (error) {
            console.error('Erreur de connexion:', error);
            
            // Gestion des erreurs spécifiques retournées par l'API
            const errorMessage = error.message.toLowerCase();
            
            if (errorMessage.includes('email')) {
              setFieldError('email', 'Email incorrect');
            } else if (errorMessage.includes('password') || errorMessage.includes('mot de passe')) {
              setFieldError('password', 'Mot de passe incorrect');
            } else if (errorMessage.includes('incorrect') || errorMessage.includes('invalide')) {
              setErrors({ submit: 'Email ou mot de passe incorrect' });
            } else {
              setErrors({ submit: error.message });
            }
          } finally {
            setSubmitting(false);
          }
        }}
      >
        {({ errors, handleBlur, handleChange, handleSubmit, isSubmitting, touched, values }) => (
          <form noValidate onSubmit={handleSubmit}>
            <Grid container spacing={3}>
              {/* Email */}
              <Grid item xs={12}>
                <Stack spacing={1}>
                  <InputLabel htmlFor="email-login">Adresse Email</InputLabel>
                  <OutlinedInput
                    id="email-login"
                    type="email"
                    value={values.email}
                    name="email"
                    onBlur={handleBlur}
                    onChange={handleChange}
                    placeholder="Entrez votre adresse email"
                    fullWidth
                    error={Boolean(touched.email && errors.email)}
                  />
                </Stack>
                {touched.email && errors.email && (
                  <FormHelperText error id="standard-weight-helper-text-email-login">
                    {errors.email}
                  </FormHelperText>
                )}
              </Grid>

              {/* Password */}
              <Grid item xs={12}>
                <Stack spacing={1}>
                  <InputLabel htmlFor="password-login">Mot de passe</InputLabel>
                  <OutlinedInput
                    fullWidth
                    color={capsWarning ? 'warning' : 'primary'}
                    error={Boolean(touched.password && errors.password)}
                    id="password-login"
                    type={showPassword ? 'text' : 'password'}
                    value={values.password}
                    name="password"
                    onBlur={(event) => {
                      setCapsWarning(false);
                      handleBlur(event);
                    }}
                    onKeyDown={onKeyDown}
                    onChange={handleChange}
                    endAdornment={
                      <InputAdornment position="end">
                        <IconButton
                          aria-label="basculer la visibilité du mot de passe"
                          onClick={handleClickShowPassword}
                          onMouseDown={handleMouseDownPassword}
                          edge="end"
                          color="secondary"
                        >
                          {showPassword ? <EyeOutlined /> : <EyeInvisibleOutlined />}
                        </IconButton>
                      </InputAdornment>
                    }
                    placeholder="Entrez votre mot de passe"
                  />
                </Stack>
                {touched.password && errors.password && (
                  <FormHelperText error id="standard-weight-helper-text-password-login">
                    {errors.password}
                  </FormHelperText>
                )}
                {capsWarning && (
                  <Typography variant="caption" sx={{ color: 'warning.main' }}>
                    Attention : Caps Lock est activé
                  </Typography>
                )}
              </Grid>

              {/* Remember me */}
              <Grid item xs={12} sx={{ mt: -1 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={checked}
                        onChange={(event) => setChecked(event.target.checked)}
                        name="checked"
                        color="primary"
                        size="small"
                      />
                    }
                    label={<Typography variant="h6">Se souvenir de moi</Typography>}
                  />
                  {/* TODO: Ajouter lien "Mot de passe oublié" plus tard */}
                </Stack>
              </Grid>

              {/* Error Message */}
              {errors.submit && (
                <Grid item xs={12}>
                  <Alert severity="error">
                    {errors.submit}
                  </Alert>
                </Grid>
              )}

              {/* Submit Button */}
              <Grid item xs={12}>
                <AnimateButton>
                  <Button
                    disableElevation
                    disabled={isSubmitting}
                    fullWidth
                    size="large"
                    type="submit"
                    variant="contained"
                    color="primary"
                  >
                    {isSubmitting ? 'Connexion...' : 'Se connecter'}
                  </Button>
                </AnimateButton>
              </Grid>
            </Grid>
          </form>
        )}
      </Formik>
    </>
  );
}