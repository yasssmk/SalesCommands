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
  // 1) Erreur réseau
  if (!axiosError?.response) return 'Network error. Please check your connection.';

  const { status, data } = axiosError.response;

  // 2) 500+
  if (status >= 500) return 'Server Error';

  // 3) DRF/Custom: detail (très courant)
  if (data?.detail && typeof data.detail === 'string') return data.detail;

  // 4) Ton format standard: { error: "..." }
  if (typeof data?.error === 'string') return data.error;

  // 5) Ton format standard (array): { error: ["..."] }
  if (Array.isArray(data?.error) && data.error.length) {
    const first = data.error[0];
    if (typeof first === 'string') return first;
    if (first && typeof first === 'object') {
      // ex: [{message:"..."}]
      return first.message || JSON.stringify(first);
    }
  }

  // 6) Ton format alternatif: { message: "..." }
  if (typeof data?.message === 'string') return data.message;

  // 7) DRF validation dict: { field: ["msg"] , ... }
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const keys = Object.keys(data);
    if (keys.length) {
      const firstVal = data[keys[0]];
      if (Array.isArray(firstVal) && firstVal.length && typeof firstVal[0] === 'string') {
        return firstVal[0];
      }
      if (typeof firstVal === 'string') return firstVal;
    }
  }

  // 8) DRF array root: ["msg", ...]
  if (Array.isArray(data) && data.length) {
    if (typeof data[0] === 'string') return data[0];
  }

  // 9) Fallback
  return `Request failed (${status})`;
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