'use client';
import PropTypes from 'prop-types';

// SWR
import { SWRConfig } from 'swr';

// SWR fetcher global
import swrFetcher from '../utils/swrFetcher';

// project import
import ThemeCustomization from '../themes';

import Locales from 'components/Locales';
import ScrollTop from 'components/ScrollTop';
import RTLLayout from 'components/RTLLayout';
import Snackbar from 'components/@extended/Snackbar';
import Notistack from 'components/third-party/Notistack';

import { ConfigProvider } from '../contexts/ConfigContext';
import { AuthProvider } from '../hooks/useAuth';

// ==============================|| SWR config||============================== //

/**
 * Configuration globale SWR
 * Centralise toutes les options communes pour éviter la duplication
 */
const swrGlobalConfig = {
  // Fetcher par défaut pour tous les hooks
  fetcher: swrFetcher,
  
  // Options de cache
  dedupingInterval: 2000,        // Évite les requêtes dupliquées pendant 2s
  keepPreviousData: true,         // Garde les données précédentes pendant le rechargement
  
  // Options de revalidation - IDENTIQUES à celles actuellement dupliquées
  revalidateIfStale: false,       // Pas de revalidation automatique si données périmées
  revalidateOnFocus: false,       // Pas de revalidation au focus de la fenêtre
  revalidateOnReconnect: false,   // Pas de revalidation à la reconnexion réseau
  
  // Gestion d'erreurs
  shouldRetryOnError: false,      // Pas de retry automatique en cas d'erreur
  errorRetryInterval: 5000,       // Si retry activé, attendre 5s
  errorRetryCount: 1,             // Si retry activé, 1 seule tentative
  
  // Callbacks globaux (optionnels, pour monitoring)
  onError: (error, key) => {
    if (process.env.NODE_ENV === 'development') {
      console.error('[SWR Global Error]', {
        key,
        error: error?.message || error
      });
    }
  },
  
  onSuccess: (data, key) => {
    if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEBUG_SWR === 'true') {
      console.debug('[SWR Global Success]', {
        key,
        dataKeys: data ? Object.keys(data) : null
      });
    }
  }
};


// ==============================|| APP - THEME, ROUTER, LOCAL ||============================== //

export default function ProviderWrapper({ children }) {
  return (
    <ConfigProvider>
      <ThemeCustomization>
        <AuthProvider>
          <SWRConfig value={swrGlobalConfig}>
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
          </SWRConfig>
        </AuthProvider>
      </ThemeCustomization>
    </ConfigProvider>
  );
}

ProviderWrapper.propTypes = { children: PropTypes.node };
