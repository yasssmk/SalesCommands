'use client';
import PropTypes from 'prop-types';

import { useEffect } from 'react';

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
import BreadcrumbBar from 'components/BreadcrumbBar';
import WorkspaceDrawer from 'components/WorkspaceDrawer';
import { BreadcrumbProvider } from 'contexts/BreadcrumbContext';
import { WorkspaceDrawerProvider } from 'contexts/WorkspaceDrawerContext';
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
    {/* WorkspaceDrawerProvider at the LAYOUT level (UX Activity L2): the single
        coque state now covers EVERY view — lists and workspaces alike — so any
        page can openDrawer(node). It renders no DOM of its own; the visual coque
        is the <WorkspaceDrawer /> sibling below. */}
    <WorkspaceDrawerProvider>
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
          {/* The single contextual breadcrumb bar — always present, constant
              height (anchor). Each page declares its trail via useBreadcrumb;
              the legacy menu-derived @extended/Breadcrumbs was removed in L1. */}
          <BreadcrumbBar />

          {/* Screen splits BELOW the breadcrumb: a flex-row [page content][coque].
              The breadcrumb above stays full-width (never pushed by the coque);
              the coque PUSHES the page content on large screens (shrinks the
              flex-grow column) and renders as an overlay on narrow screens. No
              hardcoded offset — the row sits under the breadcrumb structurally,
              so alignment holds on every view (UX Activity L2). */}
          <Box
            data-testid="content-coque-row"
            sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, flexGrow: 1, minWidth: 0 }}
          >
            <Box sx={{ flexGrow: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
              {children}
            </Box>
            <WorkspaceDrawer />
          </Box>

          <Footer />
        </Container>
      </Box>
      {/* <AddCustomer /> */}
    </Stack>
    </WorkspaceDrawerProvider>
    </BreadcrumbProvider>
    </QueryClientProvider>
  );
}

DashboardLayout.propTypes = { children: PropTypes.node };
