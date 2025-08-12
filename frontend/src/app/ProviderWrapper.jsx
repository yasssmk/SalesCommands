'use client';
import PropTypes from 'prop-types';

// next
// import { SessionProvider } from 'next-auth/react';

// project import
import ThemeCustomization from '../themes';

import Locales from 'components/Locales';
import ScrollTop from 'components/ScrollTop';
import RTLLayout from 'components/RTLLayout';
import Snackbar from 'components/@extended/Snackbar';
import Notistack from 'components/third-party/Notistack';

import { ConfigProvider } from '../contexts/ConfigContext';
import { AuthProvider } from '../hooks/useAuth';

// ==============================|| APP - THEME, ROUTER, LOCAL ||============================== //

export default function ProviderWrapper({ children }) {
  return (
    <ConfigProvider>
      <ThemeCustomization>
        <AuthProvider>
          <RTLLayout>
            <Locales>
              <ScrollTop>
                  <Notistack>
                    <Snackbar />
                    {children}
                  </Notistack>
              </ScrollTop>
            </Locales>
          </RTLLayout>
        </AuthProvider>
      </ThemeCustomization>
    </ConfigProvider>
  );
}

ProviderWrapper.propTypes = { children: PropTypes.node };
