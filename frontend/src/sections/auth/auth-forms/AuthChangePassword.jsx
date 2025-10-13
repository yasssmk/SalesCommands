// frontend/src/sections/auth/auth-forms/AuthChangePassword.jsx

'use client';

import PropTypes from 'prop-types';
import { useEffect, useState } from 'react';

// next
import { useRouter } from 'next/navigation';

// material-ui
import Button from '@mui/material/Button';
import FormHelperText from '@mui/material/FormHelperText';
import FormControl from '@mui/material/FormControl';
import Grid from '@mui/material/Unstable_Grid2';
import InputAdornment from '@mui/material/InputAdornment';
import InputLabel from '@mui/material/InputLabel';
import OutlinedInput from '@mui/material/OutlinedInput';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';

// third party
import * as Yup from 'yup';
import { Formik } from 'formik';

// project import
import IconButton from 'components/@extended/IconButton';
import AnimateButton from 'components/@extended/AnimateButton';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';
import { changePassword } from 'api/admin/users';
import { strengthColor, strengthIndicator } from 'utils/password-strength';

// assets
import EyeOutlined from '@ant-design/icons/EyeOutlined';
import EyeInvisibleOutlined from '@ant-design/icons/EyeInvisibleOutlined';

// ============================|| AUTH - CHANGE PASSWORD ||============================ //

export default function AuthChangePassword({ userId, userEmail }) {
  const router = useRouter();

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [level, setLevel] = useState();
  
  const handleClickShowPassword = () => {
    setShowPassword(!showPassword);
  };
  
  const handleClickShowConfirmPassword = () => {
    setShowConfirmPassword(!showConfirmPassword);
  };

   const updateStrength = (value) => {
    const temp = strengthIndicator(value);
    setLevel(strengthColor(temp));
  };

  useEffect(() => {
    updateStrength('');
  }, []);

  const handleMouseDownPassword = (event) => {
    event.preventDefault();
  };

  return (
    <Formik
      initialValues={{
        password: '',
        confirmPassword: '',
        submit: null
      }}
      validationSchema={Yup.object().shape({
        password: Yup.string()
          .required('Password is required')
          .min(1, 'Password must be at least 1 character'), // Pas de règle de complexité selon les specs
        confirmPassword: Yup.string()
          .required('Confirm Password is required')
          .oneOf([Yup.ref('password'), null], 'Passwords must match')
      })}
      onSubmit={async (values, { setErrors, setStatus, setSubmitting }) => {
        try {
          setSubmitting(true);
          
          // Appel API pour changer le mot de passe
          const result = await changePassword(userId, values.password, values.confirmPassword);
          
          if (result.success) {
            setStatus({ success: true });
            
            // Notification de succès
            displaySuccessSnackbar(result.message || 'Password changed successfully');
            
            // Redirection après 1.5 secondes
            setTimeout(() => {
              router.push('/admin/users');
            }, 1500);
            
          } else {
            // Gestion des erreurs de l'API
            setErrors({ submit: result.error || 'Failed to change password' });
            setStatus({ success: false });
            displayErrorSnackbar(result);
          }
        } catch (err) {
          console.error('Password change error:', err);
          setStatus({ success: false });
          setErrors({ submit: err.message || 'An unexpected error occurred' });
          displayErrorSnackbar(err);
        } finally {
          setSubmitting(false);
        }
      }}
    >
      {({ errors, handleBlur, handleChange, handleSubmit, isSubmitting, touched, values }) => (
        <form noValidate onSubmit={handleSubmit}>
          <Grid container spacing={3}>
            {/* Info utilisateur */}
            {userEmail && (
              <Grid xs={12}>
                <Box sx={{ 
                  p: 2, 
                  bgcolor: 'background.paper', 
                  borderRadius: 1,
                  border: '1px solid',
                  borderColor: 'divider'
                }}>
                  <Typography variant="body2" color="text.secondary">
                    Changing password for:
                  </Typography>
                  <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                    {userEmail}
                  </Typography>
                </Box>
              </Grid>
            )}
            
            {/* Nouveau mot de passe */}
            <Grid xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="password-change">New Password</InputLabel>
                <OutlinedInput
                  fullWidth
                  error={Boolean(touched.password && errors.password)}
                  id="password-change"
                  type={showPassword ? 'text' : 'password'}
                  value={values.password}
                  name="password"
                  onBlur={handleBlur}
                  onChange={(e) => {
                    handleChange(e);
                    updateStrength(e.target.value);
                  }}
                  endAdornment={
                    <InputAdornment position="end">
                      <IconButton
                        aria-label="toggle password visibility"
                        onClick={handleClickShowPassword}
                        onMouseDown={handleMouseDownPassword}
                        edge="end"
                        color="secondary"
                      >
                        {showPassword ? <EyeOutlined /> : <EyeInvisibleOutlined />}
                      </IconButton>
                    </InputAdornment>
                  }
                  placeholder="Enter new password"
                />
              </Stack>
              {touched.password && errors.password && (
                <FormHelperText error id="helper-text-password-change">
                  {errors.password}
                </FormHelperText>
              )}
              <FormControl fullWidth sx={{ mt: 2 }}>
                <Grid container spacing={2} alignItems="center">
                  <Grid >
                    <Box sx={{ bgcolor: level?.color, width: 85, height: 8, borderRadius: '7px' }} />
                  </Grid>
                  <Grid >
                    <Typography variant="subtitle1" fontSize="0.75rem">
                      {level?.label}
                    </Typography>
                  </Grid>
                </Grid>
              </FormControl>
            </Grid>
            
            {/* Confirmation du mot de passe */}
            <Grid xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="confirm-password-change">Confirm New Password</InputLabel>
                <OutlinedInput
                  fullWidth
                  error={Boolean(touched.confirmPassword && errors.confirmPassword)}
                  id="confirm-password-change"
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={values.confirmPassword}
                  name="confirmPassword"
                  onBlur={handleBlur}
                  onChange={handleChange}
                  endAdornment={
                    <InputAdornment position="end">
                      <IconButton
                        aria-label="toggle password visibility"
                        onClick={handleClickShowConfirmPassword}
                        onMouseDown={handleMouseDownPassword}
                        edge="end"
                        color="secondary"
                      >
                        {showConfirmPassword ? <EyeOutlined /> : <EyeInvisibleOutlined />}
                      </IconButton>
                    </InputAdornment>
                  }
                  placeholder="Confirm new password"
                />
              </Stack>
              {touched.confirmPassword && errors.confirmPassword && (
                <FormHelperText error id="helper-text-confirm-password-change">
                  {errors.confirmPassword}
                </FormHelperText>
              )}
            </Grid>

            {/* Message d'erreur général */}
            {errors.submit && (
              <Grid xs={12} >
                <FormHelperText error>{errors.submit}</FormHelperText>
              </Grid>
            )}
            
            {/* Boutons d'action */}
            <Grid xs={12}>
              <Stack direction="row" spacing={2}>
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
                    Change Password
                  </Button>
                </AnimateButton>
                
                <AnimateButton>
                  <Button 
                    disableElevation 
                    fullWidth 
                    size="large" 
                    variant="outlined"
                    color="secondary"
                    onClick={() => router.push('/admin/users')}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                </AnimateButton>
              </Stack>
            </Grid>
          </Grid>
        </form>
      )}
    </Formik>
  );
}

AuthChangePassword.propTypes = {
  userId: PropTypes.string.isRequired,
  userEmail: PropTypes.string
};