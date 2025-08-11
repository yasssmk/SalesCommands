// frontend/src/utils/errorHandler.js

/**
 * ✅ GESTIONNAIRE D'ERREURS MVP - Ultra simple
 * 
 * Extraction directe des messages du backend Django
 * Utilisable sur toutes les requêtes API
 */

// ==============================|| MAIN ERROR HANDLER ||============================== //

/**
 * ✅ EXTRACTION DIRECTE DU MESSAGE BACKEND DJANGO
 * @param {Error} axiosError - Erreur Axios complète
 * @returns {string} Message d'erreur à afficher
 */
export const handleApiError = (axiosError) => {
  // Erreur réseau (pas de response)
  if (!axiosError.response) {
    return 'Network error. Please check your connection.';
  }
  
  // Erreur serveur 500+
  if (axiosError.response.status >= 500) {
    return 'Server Error';
  }
  
  const backendData = axiosError.response.data;
  
  // Structure StandardizedValidationError Django : { "error": "message" }
  if (backendData?.error && typeof backendData.error === 'string') {
    return backendData.error;
  }
  
  // Structure alternative : { "message": "..." }
  if (backendData?.message && typeof backendData.message === 'string') {
    return backendData.message;
  }
  
  // Structure validation détaillée : { "error": { "field": ["messages"] } }
  if (backendData?.error && typeof backendData.error === 'object') {
    const firstFieldErrors = Object.values(backendData.error)[0];
    if (Array.isArray(firstFieldErrors) && firstFieldErrors.length > 0) {
      return firstFieldErrors[0];
    }
  }
  
  // Fallback
  return `Request failed (${axiosError.response.status})`;
};

// ==============================|| FORMIK INTEGRATION ||============================== //

/**
 * ✅ HANDLER POUR FORMIK
 * @param {Error} axiosError - Erreur Axios
 * @param {Function} setErrors - setErrors de Formik
 * @param {Function} setSubmitting - setSubmitting de Formik
 */
export const handleFormError = (axiosError, setErrors, setSubmitting) => {
  const errorMessage = handleApiError(axiosError);
  setErrors({ submit: errorMessage });
  setSubmitting(false);
};