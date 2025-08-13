import { useMemo } from 'react';

// project import - Structure menu officielle
import menuItems from '../menu-items';

// ==============================|| INITIAL STATE ||============================== //

const initialState = {
  openedItem: 'dashboard',
  openedComponent: 'buttons',
  openedHorizontalItem: null,
  isDashboardDrawerOpened: false,
  isComponentDrawerOpened: true
};

// ==============================|| HOOKS - Compatible avec Modèle ||============================== //

/**
 * Hook pour récupérer les données menu - Compatible API modèle
 * Utilise notre structure menu-items officielle
 */
export function useGetMenu() {
  const memoizedValue = useMemo(() => {
    return {
      menu: menuItems, // Utilise la vraie structure menu-items
      menuLoading: false,
      menuError: null,
      menuValidating: false,
      menuEmpty: false
    };
  }, []);

  return memoizedValue;
}

/**
 * Hook pour état master - Retourne état initial statique
 * Les composants utilisent directement useMenuState depuis hooks/
 */
export function useGetMenuMaster() {
  const memoizedValue = useMemo(
    () => ({
      menuMaster: initialState,
      menuMasterLoading: false
    }),
    []
  );

  return memoizedValue;
}