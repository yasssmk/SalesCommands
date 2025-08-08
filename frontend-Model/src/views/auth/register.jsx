'use client';

// next
import Link from 'next/link';
import { getProviders, getCsrfToken, useSession } from 'next-auth/react';

// material-ui
import Grid from '@mui/material/Grid';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project import
import AuthWrapper from 'sections/auth/AuthWrapper';
import AuthRegister from 'sections/auth/auth-forms/AuthRegister';

// ================================|| REGISTER ||================================ //

export default function Register() {
  const { data: session } = useSession();
  const csrfToken = getCsrfToken();
  const providers = getProviders();

  return (
    <AuthWrapper>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Stack direction="row" justifyContent="space-between" alignItems="baseline" sx={{ mb: { xs: -0.5, sm: 0.5 } }}>
            <Typography variant="h3">Sign up</Typography>
            <Link href={session ? '/pages/login' : '/login'}  >
              <Link variant="body1" color="primary">
                Already have an account?
              </Link>
            </Link>
          </Stack>
        </Grid>
        <Grid item xs={12}>
          <AuthRegister providers={providers} csrfToken={csrfToken} />
        </Grid>
      </Grid>
    </AuthWrapper>
  );
}
