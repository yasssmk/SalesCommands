'use client';

/**
 * Clés partagées pour le cache SWR et la persistance localStorage.
 * - SWR_KEY_MASTER : identifiant unique du "store" menu dans SWR (aligné sur le modèle Mantis)
 * - LS_KEY_DASHBOARD_DRAWER : clé de persistance de l'état du drawer (ouvert/fermé)
 */

export const SWR_KEY_MASTER = 'api/menu/master';
export const LS_KEY_DASHBOARD_DRAWER = 'dashboard_drawer_open';