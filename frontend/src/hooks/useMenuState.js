'use client';

/**
 * Store global (SWR) pour l'état du drawer — sans dépendre de api/menu.
 * - Une seule source de vérité partagée via SWR (clé interne)
 * - Persistance de isDashboardDrawerOpened dans localStorage
 * - API simple/compatible : { menuMaster, menuMasterLoading, handlerDrawerOpen, toggleDrawer, ... }
 */

import { useEffect, useMemo, useCallback } from 'react';
import useSWR, { mutate } from 'swr';
import { SWR_KEY_MASTER, LS_KEY_DASHBOARD_DRAWER } from 'config/swr';

// État initial compatible avec le modèle
const INITIAL_MENU_MASTER = {
  openedItem: 'dashboard',
  openedComponent: 'buttons',
  openedHorizontalItem: null,
  isDashboardDrawerOpened: false,
  isComponentDrawerOpened: true
};

// ===== utils =====
function readPersistedDrawerOpen() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(LS_KEY_DASHBOARD_DRAWER); // ✅ bonne constante
    if (raw == null) return null;
    return Boolean(JSON.parse(raw));
  } catch {
    return null;
  }
}

function writePersistedDrawerOpen(open) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(LS_KEY_DASHBOARD_DRAWER, JSON.stringify(Boolean(open))); // ✅ bonne constante
  } catch {
    // ignore
  }
}

// ===== hook principal =====
export function useMenuState() {
  // 1) Seed le cache SWR si vide (à partir du localStorage)
  useEffect(() => {
    mutate(
      SWR_KEY_MASTER,
      (current) => {
        if (current) return current;
        const persisted = readPersistedDrawerOpen();
        return {
          ...INITIAL_MENU_MASTER,
          isDashboardDrawerOpened:
            persisted === null ? INITIAL_MENU_MASTER.isDashboardDrawerOpened : persisted
        };
      },
      false // pas de revalidation réseau
    );
  }, []);

  // 2) Lire la valeur depuis SWR (pas de fetcher : on lit uniquement le cache local)
  const { data } = useSWR(SWR_KEY_MASTER, null, {
    revalidateIfStale: false,
    revalidateOnFocus: false,
    revalidateOnReconnect: false
  });

  const menuMaster = data || INITIAL_MENU_MASTER;
  const menuMasterLoading = !data; // au premier render avant le seed effect

  // 🔄 3) Synchroniser automatiquement le localStorage à chaque changement d'état
  useEffect(() => {
    writePersistedDrawerOpen(menuMaster.isDashboardDrawerOpened);
  }, [menuMaster.isDashboardDrawerOpened]);

  // 4) Mutations — mettent à jour tout le monde via SWR
  const setDrawerState = useCallback((open) => {
    mutate(
      SWR_KEY_MASTER,
      (current) => ({
        ...(current || INITIAL_MENU_MASTER),
        isDashboardDrawerOpened: Boolean(open)
      }),
      false
    );
  }, []);

  const toggleDrawer = useCallback(() => {
    mutate(
      SWR_KEY_MASTER,
      (current) => {
        const base = current || INITIAL_MENU_MASTER;
        return { ...base, isDashboardDrawerOpened: !base.isDashboardDrawerOpened };
      },
      false
    );
  }, []);

  const openDrawer = useCallback(() => setDrawerState(true), [setDrawerState]);
  const closeDrawer = useCallback(() => setDrawerState(false), [setDrawerState]);
  const handlerDrawerOpen = useCallback((state) => setDrawerState(state), [setDrawerState]);

  // 5) API exposée
  return useMemo(
    () => ({
      // États compatibles
      menuMaster,
      menuMasterLoading,

      // Accès direct pratique
      drawerOpen: menuMaster.isDashboardDrawerOpened,
      isLoading: menuMasterLoading,

      // Actions
      toggleDrawer,
      openDrawer,
      closeDrawer,
      setDrawerState,

      // Compat modèle
      handlerDrawerOpen
    }),
    [menuMaster, menuMasterLoading, toggleDrawer, openDrawer, closeDrawer, setDrawerState, handlerDrawerOpen]
  );
}

export default useMenuState;
