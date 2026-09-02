'use client';
import PropTypes from 'prop-types';

import { useEffect } from 'react';

// next
import { usePathname } from 'next/navigation';

import useMediaQuery from '@mui/material/useMediaQuery';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Toolbar from '@mui/material/Toolbar';
import Stack from '@mui/material/Stack';

// project import
import Drawer from './Drawer';
import Header from './Header';
import Footer from './Footer';
import HorizontalBar from './Drawer/HorizontalBar';
import Loader from 'components/Loader';
import Breadcrumbs from 'components/@extended/Breadcrumbs';
import BreadcrumbBar from 'components/BreadcrumbBar';
import { BreadcrumbProvider } from 'contexts/BreadcrumbContext';
// import AddCustomer from 'sections/apps/customer/AddCustomer';

import { MenuOrientation } from 'config';
import useConfig from 'hooks/useConfig';
import { useMenuState } from 'hooks/useMenuState';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export default function DashboardLayout({ children }) {
  const { menuMasterLoading } = useMenuState();
  const pathname = usePathname();
  const downXL = useMediaQuery((theme) => theme.breakpoints.down('xl'));
  const downLG = useMediaQuery((theme) => theme.breakpoints.down('lg'));

  const { container, miniDrawer, menuOrientation } = useConfig();

  const isHorizontal = menuOrientation === MenuOrientation.HORIZONTAL && !downLG;

  // // set media wise responsive drawer
  // useEffect(() => {
  //   if (!miniDrawer) {
  //     handlerDrawerOpen(!downXL);
  //   }
  //   // eslint-disable-next-line react-hooks/exhaustive-deps
  // }, [downXL]);

  if (menuMasterLoading) return <Loader />;

  return (
    <QueryClientProvider client={queryClient}>
    {/* BreadcrumbProvider wraps BOTH the bar and the pages (children) so a
        page's setCrumbs push reaches the SAME provider the bar reads — no
        two-instances trap (UX Activity L0). */}
    <BreadcrumbProvider>
    <Stack direction="row" width={1}>
      <Header />
      {!isHorizontal ? <Drawer /> : <HorizontalBar />}
      <Box component="main" sx={{   width: 'calc(100% - 260px)', flexGrow: 1, p: { xs: 2, sm: 3 } }}>
        <Toolbar sx={{ mt: isHorizontal ? 8 : 'inherit' }} />
        <Container
          maxWidth={container ? 'xl' : false}
          sx={{
            ...(container && { px: { xs: 0, sm: 2 } }),
            position: 'relative',
            minHeight: 'calc(100vh - 110px)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Single contextual breadcrumb bar — always present, constant height
              (anchor). Coexists with the legacy @extended/Breadcrumbs in L0; L1
              removes the legacy. */}
          <BreadcrumbBar />
          {pathname !== '/apps/profiles/account/my-account' && pathname !== '/'  && <Breadcrumbs />}
          {children}
          <Footer />
        </Container>
      </Box>
      {/* <AddCustomer /> */}
    </Stack>
    </BreadcrumbProvider>
    </QueryClientProvider>
  );
}

DashboardLayout.propTypes = { children: PropTypes.node };
