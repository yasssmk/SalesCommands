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

  // ==============================
  // NETWORK ERROR (Backend down, DNS failure, etc.)
  // ==============================
  // Detect genuine Axios network errors FIRST before checking .error/.message
  if (!axiosError?.response) {
    // Check if it's a genuine Axios network error (not a custom error object)
    const isAxiosNetworkError = 
      axiosError?.message === 'Network Error' || 
      axiosError?.code === 'ERR_NETWORK' ||
      axiosError?.code === 'ECONNREFUSED';
    
    if (isAxiosNetworkError) {
      // ✅ Use front-end message for true network errors
      return 'Unable to connect to the server. Please check your internet connection.';
    }
    
    // For other cases without response, check custom error properties
    // (e.g. from apiRequest wrapper for specific scenarios)
    if (axiosError.error && typeof axiosError.error === 'string') {
      return axiosError.error;
    }
    
    if (axiosError.message && typeof axiosError.message === 'string') {
      return axiosError.message;
    }
    
    // Final fallback for unknown no-response errors
    return 'Network error. Please check your connection.';
  }

  // ==============================
  //  Network Error Detection
  // ==============================

  const { status, data } = axiosError.response;

  // 2) 500+
  if (status >= 500) {
    if (status === 503) {
      return 'Service temporarily unavailable. Please try again shortly.';
    }
    if (status === 502) {
      return 'Bad gateway. The server is temporarily unavailable.';
    }
    if (status === 504) {
      return 'Gateway timeout. The server took too long to respond.';
    }
    // Generic 500
    return 'Server error. Please try again later.';
  }

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
  if (status >= 400 && status < 500) {
    // Validation errors
    if (status === 400 || status === 422) {
      return 'Validation error. Please review your input.';
    }
    
    // Authentication required
    if (status === 401) {
      return 'Authentication required. Please sign in again.';
    }
    
    // Permission denied
    if (status === 403) {
      return 'You do not have permission to perform this action.';
    }
    
    // Resource not found
    if (status === 404) {
      return 'Resource not found.';
    }
    
    // Generic 4xx fallback (for other client errors like 409, 418, etc.)
    return 'Request failed. Please check your input and try again.';
  }

  // ==============================
  // Final Fallback
  // ==============================
  // Should rarely be reached (only for unknown status codes or edge cases)
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