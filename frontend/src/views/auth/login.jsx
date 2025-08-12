'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// next
import Link from 'next/link';

// material-ui
import Grid from '@mui/material/Unstable_Grid2';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project import
import AuthWrapper from 'sections/auth/AuthWrapper';
import AuthLogin from 'sections/auth/auth-forms/AuthLogin';

// CHANGEMENT: Utiliser le hook useAuth au lieu de isAuthenticated
import { useAuth } from 'hooks/useAuth';
import Loader from 'components/Loader';

// ==============================|| LOGIN PAGE ||============================== //

export default function SignIn() {
  
  const { isAuthenticated, isLoading } = useAuth();

  if (isAuthenticated) {
    return null; 
  }

  // Mock providers and csrfToken for compatibility with model structure
  const providers = null;
  const csrfToken = null;

  return (
    <AuthWrapper>
      <Grid container spacing={3}>
        <Grid xs={12}>
          <Stack direction="row" justifyContent="space-between" alignItems="baseline" sx={{ mb: { xs: -0.5, sm: 0.5 } }}>
            <Typography variant="h3">Login</Typography>
            <Link href="/register" style={{ textDecoration: 'none' }}>
              <Typography variant="body1" color="primary" sx={{ cursor: 'pointer' }}>
                Don&apos;t have an account?
              </Typography>
            </Link>
          </Stack>
        </Grid>
        <Grid xs={12}>
          <AuthLogin providers={providers} csrfToken={csrfToken} />
        </Grid>
      </Grid>
    </AuthWrapper>
  );
}