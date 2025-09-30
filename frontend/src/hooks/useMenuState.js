'use client';

import { useEffect, useMemo, useCallback } from 'react';
import useSWR from 'swr';
import { SWR_KEY_MASTER, LS_KEY_DASHBOARD_DRAWER } from 'config/swr';

// État initial compatible avec le modèle
const INITIAL_MENU_MASTER = {
  openedItem: 'dashboard',
  openedComponent: 'buttons',
  openedHorizontalItem: null,
  isDashboardDrawerOpened: false,
  isComponentDrawerOpened: true
};

// --- utils ---
function readPersistedDrawerOpen() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(LS_KEY_DASHBOARD_DRAWER);
    if (raw == null) return null;
    return Boolean(JSON.parse(raw));
  } catch {
    return null;
  }
}

function writePersistedDrawerOpen(open) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(LS_KEY_DASHBOARD_DRAWER, JSON.stringify(Boolean(open)));
  } catch {
    // ignore
  }
}

export function useMenuState() {
  // 1) Calculer l’état initial une seule fois (incluant la valeur persistée)
  const initialMaster = useMemo(() => {
    const persisted = readPersistedDrawerOpen();
    return {
      ...INITIAL_MENU_MASTER,
      isDashboardDrawerOpened:
        persisted === null ? INITIAL_MENU_MASTER.isDashboardDrawerOpened : persisted
    };
  }, []);

  // 2) Store SWR SANS fetcher, avec fallbackData (== seed propre, aucun setState pendant le mount)
  const { data: menuMaster, mutate } = useSWR(
    SWR_KEY_MASTER,
    null,
    {
      fallbackData: initialMaster,
      revalidateIfStale: false,
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  // 3) Persister automatiquement l’ouverture du drawer
  useEffect(() => {
    writePersistedDrawerOpen(menuMaster.isDashboardDrawerOpened);
  }, [menuMaster.isDashboardDrawerOpened]);

  // 4) Mutations via le mutate lié au hook (pas le mutate global)
  const setDrawerState = useCallback(
    (open) => {
      mutate(
        (current) => ({
          ...(current ?? initialMaster),
          isDashboardDrawerOpened: Boolean(open)
        }),
        { revalidate: false }
      );
    },
    [mutate]
  );

  const toggleDrawer = useCallback(() => {
    mutate(
      (current) => {
        const base = current ?? initialMaster;
        return { ...base, isDashboardDrawerOpened: !base.isDashboardDrawerOpened };
      },
      { revalidate: false }
    );
  }, [mutate]);

  const openDrawer = useCallback(() => setDrawerState(true), [setDrawerState]);
  const closeDrawer = useCallback(() => setDrawerState(false), [setDrawerState]);
  const handlerDrawerOpen = useCallback((state) => setDrawerState(state), [setDrawerState]);

  // ===== Handlers "compat modèle" =====
  const handlerActiveItem = useCallback(
    (openedItem) => {
      mutate((c) => ({ ...(c ?? initialMaster), openedItem }), { revalidate: false });
    },
    [mutate]
  );

  const handlerHorizontalActiveItem = useCallback(
    (openedHorizontalItem) => {
      mutate((c) => ({ ...(c ?? initialMaster), openedHorizontalItem }), { revalidate: false });
    },
    [mutate]
  );

  const handlerComponentDrawer = useCallback(
    (isComponentDrawerOpened) => {
      mutate(
        (c) => ({ ...(c ?? initialMaster), isComponentDrawerOpened: !!isComponentDrawerOpened }),
        { revalidate: false }
      );
    },
    [mutate]
  );

  const handlerActiveComponent = useCallback(
    (openedComponent) => {
      mutate((c) => ({ ...(c ?? initialMaster), openedComponent }), { revalidate: false });
    },
    [mutate]
  );

  // 5) API exposée
  const menuMasterLoading = false; // on a toujours fallbackData
  return {
    // états
    menuMaster,
    menuMasterLoading,

    // accès pratiques
    drawerOpen: menuMaster.isDashboardDrawerOpened,
    isLoading: menuMasterLoading,

    // actions drawer
    toggleDrawer,
    openDrawer,
    closeDrawer,
    setDrawerState,
    handlerDrawerOpen,

    // actions compatibles modèle
    handlerActiveItem,
    handlerHorizontalActiveItem,
    handlerComponentDrawer,
    handlerActiveComponent
  };
}

export default useMenuState;
