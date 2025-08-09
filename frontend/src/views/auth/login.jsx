'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// next
import Link from 'next/link';

// material-ui
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project import
import AuthWrapper from 'sections/auth/AuthWrapper';
import AuthLogin from 'sections/auth/auth-forms/AuthLogin';

// api
import { isAuthenticated } from 'api/auth';

// ==============================|| LOGIN PAGE ||============================== //

export default function SignIn() {
  const router = useRouter();

  // Check if user is already authenticated
  useEffect(() => {
    if (isAuthenticated()) {
      // Redirect to dashboard if already logged in
      router.push('/');
    }
  }, [router]);

  // Don't render page if already authenticated (avoid flash)
  if (isAuthenticated()) {
    return null;
  }

  return (
    <AuthWrapper>
      <Grid container spacing={3}>
        {/* Header with title and registration link */}
        <Grid item xs={12}>
          <Stack 
            direction="row" 
            justifyContent="space-between" 
            alignItems="baseline" 
            sx={{ mb: { xs: -0.5, sm: 0.5 } }}
          >
            <Typography variant="h3">Login</Typography>
            <Link href="/register" style={{ textDecoration: 'none' }}>
              <Typography variant="body1" color="primary" sx={{ cursor: 'pointer' }}>
                Don&apos;t have an account?
              </Typography>
            </Link>
          </Stack>
        </Grid>

        {/* Login form */}
        <Grid item xs={12}>
          <AuthLogin />
        </Grid>

        {/* Forgot password link */}
        <Grid item xs={12}>
          <Stack direction="row" justifyContent="center" sx={{ mt: 1 }}>
            <Typography variant="body2" color="secondary">
              Forgot password? {' '}
              <Link href="/forgot-password" style={{ textDecoration: 'none' }}>
                <Typography 
                  component="span" 
                  variant="body2" 
                  color="primary" 
                  sx={{ cursor: 'pointer' }}
                >
                  Reset here
                </Typography>
              </Link>
            </Typography>
          </Stack>
        </Grid>
      </Grid>
    </AuthWrapper>
  );
}