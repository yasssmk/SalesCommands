// frontend/src/hooks/useMenuState.js

'use client';
import { useState, useEffect, useCallback } from 'react';

// ==============================|| MENU STATE HOOK MVP ||============================== //

/**
 * Hook MVP pour gérer l'état du drawer dashboard
 * Remplace la complexité de useGetMenuMaster par une solution simple
 */
export function useMenuState() {
  // État local du drawer (ouvert/fermé)
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [isLoading, setIsLoading] = useState(false);

  // ==============================|| PERSISTANCE LOCALSTORAGE ||============================== //

  // Charger l'état depuis localStorage au montage
  useEffect(() => {
    try {
      const savedState = localStorage.getItem('dashboard_drawer_open');
      if (savedState !== null) {
        setDrawerOpen(JSON.parse(savedState));
      }
    } catch (error) {
      console.warn('Error loading drawer state from localStorage:', error);
      // Fallback sur état par défaut (true)
    }
  }, []);

  // Sauvegarder l'état dans localStorage à chaque changement
  useEffect(() => {
    try {
      localStorage.setItem('dashboard_drawer_open', JSON.stringify(drawerOpen));
    } catch (error) {
      console.warn('Error saving drawer state to localStorage:', error);
    }
  }, [drawerOpen]);

  // ==============================|| ACTIONS ||============================== //

  /**
   * Toggle l'état du drawer (ouvert <-> fermé)
   */
  const toggleDrawer = useCallback(() => {
    setDrawerOpen(prev => !prev);
  }, []);

  /**
   * Ouvrir le drawer
   */
  const openDrawer = useCallback(() => {
    setDrawerOpen(true);
  }, []);

  /**
   * Fermer le drawer
   */
  const closeDrawer = useCallback(() => {
    setDrawerOpen(false);
  }, []);

  /**
   * Définir l'état du drawer explicitement
   * @param {boolean} open - Nouvel état du drawer
   */
  const setDrawerState = useCallback((open) => {
    setDrawerOpen(Boolean(open));
  }, []);

  // ==============================|| COMPATIBILITÉ AVEC useGetMenuMaster ||============================== //

  /**
   * Interface compatible avec l'ancien useGetMenuMaster
   * Permet de remplacer facilement dans les composants existants
   */
  const menuMaster = {
    isDashboardDrawerOpened: drawerOpen,
  };

  /**
   * Handler compatible avec handlerDrawerOpen du frontend-Model
   * @param {boolean} state - Nouvel état du drawer
   */
  const handlerDrawerOpen = useCallback((state) => {
    setDrawerState(state);
  }, [setDrawerState]);

  // ==============================|| RETOUR ||============================== //

  return {
    // États
    drawerOpen,
    isLoading, // Toujours false pour MVP, compatible avec menuMasterLoading
    
    // Actions simples
    toggleDrawer,
    openDrawer,
    closeDrawer,
    setDrawerState,
    
    // Compatibilité avec l'ancien système
    menuMaster,
    handlerDrawerOpen,
    
    // Alias pour compatibilité
    menuMasterLoading: isLoading,
  };
}

// ==============================|| EXPORT COMPATIBLE ||============================== //

/**
 * Export pour compatibilité avec l'ancien système
 * Permet d'importer { useGetMenuMaster } et { handlerDrawerOpen }
 */
// export const useGetMenuMaster = useMenuState;

// /**
//  * Handler global exporté pour compatibilité
//  */
// export const handlerDrawerOpen = (state) => {
//   // Cette fonction sera surchargée par le hook dans les composants
//   console.warn('handlerDrawerOpen called without context. Use the hook version instead.');
// };

// export default useMenuState;