// frontend/src/views/admin/users/change-password.jsx
// VERSION SIMPLE - Fidèle au modèle

'use client';

import { useParams } from 'next/navigation';

// material-ui
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project import
import AuthWrapper from 'sections/auth/AuthWrapper';
import AuthChangePassword from 'sections/auth/auth-forms/AuthChangePassword';

// ================================|| CHANGE PASSWORD ||================================ //

export default function ChangePasswordView() {
  const params = useParams();
  const userId = params?.id;

  console.log('Params:', params); // Debug
  console.log('UserId:', userId); 

  return (
    <AuthWrapper>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Stack sx={{ mb: { xs: -0.5, sm: 0.5 } }} spacing={1}>
            <Typography variant="h3">Change Password</Typography>
            <Typography color="secondary">Please choose a new password for the user</Typography>
          </Stack>
        </Grid>
        <Grid item xs={12}>
          <AuthChangePassword userId={userId} />
        </Grid>
      </Grid>
    </AuthWrapper>
  );
}