// frontend/src/utils/snackbar.js
// ✅ HELPER STANDARDISÉ pour uniformiser tous les snackbars de l'app

import { openSnackbar as openSnackbarBase } from 'api/snackbar';

/**
 * ✅ RÈGLES STANDARD DE DURÉE
 * 
 * - Info simple / succès rapide : 3s (lecture rapide)
 * - Succès avec détails : 4s
 * - Warning / succès partiel : 5s (plus d'infos à lire)
 * - Erreur / message important : 6s (temps de lire et comprendre)
 */
const DURATIONS = {
  SHORT: 3000,    // Messages simples (créé, supprimé, etc.)
  NORMAL: 4000,   // Succès avec détails
  WARNING: 5000,  // Warnings, succès partiels
  ERROR: 6000     // Erreurs, messages critiques
};

/**
 * ✅ POSITION STANDARD
 * Toujours top-right pour cohérence visuelle
 */
const STANDARD_ANCHOR = {
  vertical: 'top',
  horizontal: 'right'
};

/**
 * Détermine automatiquement la durée selon le type et le contenu
 */
function getAutoDuration(color, message = '', hasDetails = false) {
  // Erreurs : toujours le plus long
  if (color === 'error') return DURATIONS.ERROR;
  
  // Warnings : durée moyenne-longue
  if (color === 'warning') return DURATIONS.WARNING;
  
  // Succès avec détails (ex: "5 updated, 2 failed")
  if (hasDetails || (message && message.length > 50)) {
    return DURATIONS.NORMAL;
  }
  
  // Succès simple
  return DURATIONS.SHORT;
}

/**
 * ✅ WRAPPER STANDARDISÉ
 * 
 * Usage simple:
 * showSnackbar.success('User created')
 * showSnackbar.error('Failed to save', { duration: 7000 })
 * showSnackbar.warning('5 updated, 2 failed', { hasDetails: true })
 */
export const showSnackbar = {
  /**
   * Snackbar de succès
   */
  success: (message, options = {}) => {
    const duration = options.duration ?? getAutoDuration('success', message, options.hasDetails);
    
    openSnackbarBase({
      open: true,
      message,
      variant: 'alert',
      alert: { color: 'success' },
      anchorOrigin: options.anchorOrigin ?? STANDARD_ANCHOR,
      autoHideDuration: duration,
      ...options
    });
  },

  /**
   * Snackbar d'erreur
   */
  error: (message, options = {}) => {
    const duration = options.duration ?? DURATIONS.ERROR;
    
    openSnackbarBase({
      open: true,
      message,
      variant: 'alert',
      alert: { color: 'error' },
      anchorOrigin: options.anchorOrigin ?? STANDARD_ANCHOR,
      autoHideDuration: duration,
      ...options
    });
  },

  /**
   * Snackbar de warning
   */
  warning: (message, options = {}) => {
    const duration = options.duration ?? DURATIONS.WARNING;
    
    openSnackbarBase({
      open: true,
      message,
      variant: 'alert',
      alert: { color: 'warning' },
      anchorOrigin: options.anchorOrigin ?? STANDARD_ANCHOR,
      autoHideDuration: duration,
      ...options
    });
  },

  /**
   * Snackbar d'info
   */
  info: (message, options = {}) => {
    const duration = options.duration ?? DURATIONS.SHORT;
    
    openSnackbarBase({
      open: true,
      message,
      variant: 'alert',
      alert: { color: 'info' },
      anchorOrigin: options.anchorOrigin ?? STANDARD_ANCHOR,
      autoHideDuration: duration,
      ...options
    });
  },

  /**
   * Snackbar custom (pour cas spéciaux)
   */
  custom: (message, color, options = {}) => {
    const duration = options.duration ?? getAutoDuration(color, message, options.hasDetails);
    
    openSnackbarBase({
      open: true,
      message,
      variant: 'alert',
      alert: { color },
      anchorOrigin: options.anchorOrigin ?? STANDARD_ANCHOR,
      autoHideDuration: duration,
      ...options
    });
  }
};

/**
 * ✅ BACKWARD COMPATIBILITY
 * Garde l'ancien import possible pendant la transition
 */
export { openSnackbar as openSnackbarBase } from 'api/snackbar';

// Export par défaut du helper
export default showSnackbar;