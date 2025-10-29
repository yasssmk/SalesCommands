// frontend/src/utils/csvImportNotifications.js

/**
 * ✅ CSV Import Notifications (centralisé)
 *
 * Affiche des snackbars standardisés pour les imports CSV :
 * - Ne gère PAS l’échec total (0%) → déjà géré dans useCSVImport via handleBulkError.
 * - Gère le succès "clean" (100%) → success snackbar.
 * - Gère le succès partiel (1–99%) → warning snackbar.
 *
 * Compatible avec 2 formats de summary :
 *  - Format "bulk"    : { requested, created/updated/deleted/archived, failed, skipped }
 *  - Format "csvHook" : { total, success, failed, skipped }
 *
 * API:
 *   notifyCSVImportOutcome(response, { entityLabel, suppressSuccess, suppressWarning })
 *
 * @module utils/csvImportNotifications
 */

import { displaySuccessSnackbar, displayWarningSnackbar } from './displayError';

// ------------------------------ Helpers ------------------------------ //

const isPlainObject = (obj) =>
  obj !== null &&
  typeof obj === 'object' &&
  !Array.isArray(obj) &&
  Object.prototype.toString.call(obj) === '[object Object]';

/**
 * Extraction tolérante des compteurs (supporte les 2 formats de summary).
 * @param {object} response
 * @returns {{requested:number, success:number, failed:number, skipped:number}}
 */
function extractCounts(response) {
  const summary = isPlainObject(response?.summary) ? response.summary : {};
  const requested = Number(
    summary.requested ?? summary.total ?? 0
  );

  // successCount : priorités (bulk → csvHook)
  const success = Number(
    summary.updated ??
    summary.created ??
    summary.deleted ??
    summary.archived ??
    summary.success ??
    0
  );

  const failed = Number(summary.failed ?? 0);
  const skipped = Number(summary.skipped ?? 0);

  return { requested, success, failed, skipped };
}

/**
 * Construit un libellé concis pour le toast.
 * @param {number} success
 * @param {number} failed
 * @param {number} skipped
 * @param {string|undefined} entityLabel ex: "user(s)" (optionnel)
 */
function buildMessage(success, failed, skipped, entityLabel) {
  // Success clean
  if (failed === 0 && skipped === 0) {
    return entityLabel
      ? `${success} ${entityLabel} imported`
      : `${success} imported`;
  }

  // Partiel
  const parts = [];
  parts.push(entityLabel ? `${success} ${entityLabel} imported` : `${success} imported`);
  if (failed > 0) parts.push(`${failed} failed`);
  if (skipped > 0) parts.push(`${skipped} skipped`);
  return parts.join(', ');
}

// ------------------------------ Main API ------------------------------ //

/**
 * Affiche la notification adaptée pour un résultat d'import CSV.
 * Ne montre RIEN si échec total (0%) → déjà géré par handleBulkError dans useCSVImport.
 *
 * @param {object} response - objet renvoyé par useCSVImport (finalResponse / errorResponse)
 * @param {object} [options]
 * @param {string} [options.entityLabel] - ex: "user(s)" pour le message
 * @param {boolean} [options.suppressSuccess=false] - ne pas afficher le toast success
 * @param {boolean} [options.suppressWarning=false] - ne pas afficher le toast warning
 * @returns {{shown:boolean, kind:'none'|'success'|'warning', message?:string}}
 */
export function notifyCSVImportOutcome(response, options = {}) {
  const {
    entityLabel,
    suppressSuccess = false,
    suppressWarning = false
  } = options;

  if (!isPlainObject(response)) {
    if (process.env.NODE_ENV === 'development') {
      console.warn('[csvImportNotifications] Invalid response object:', response);
    }
    return { shown: false, kind: 'none' };
  }

  if (response?.isPending || response?.status === 'pending') {
    const msg = response?.message ||
      'Operation is still in progress. It will complete in the background.';

    displayWarningSnackbar(msg);
    return { shown: true, kind: 'warning', message: msg };
  }


  const { requested, success, failed, skipped } = extractCounts(response);

  // Détecter les cas
  const isCleanSuccess = response?.success === true && success > 0 && failed === 0 && skipped === 0;
  const isPartial = success > 0 && (failed > 0 || skipped > 0);
  const isTotalFailure = requested > 0 && success === 0; // 0% de succès

  // 0% → déjà toasté par handleBulkError dans le hook → ne rien faire ici
  if (isTotalFailure) {
    if (process.env.NODE_ENV === 'development') {
      console.log('[csvImportNotifications] Total failure detected → no extra toast (handled upstream).');
    }
    return { shown: false, kind: 'none' };
  }

  // Succès clean
  if (isCleanSuccess && !suppressSuccess) {
    const msg = buildMessage(success, failed, skipped, entityLabel);
    displaySuccessSnackbar(msg);
    return { shown: true, kind: 'success', message: msg };
  }

  // Succès partiel
  if (isPartial && !suppressWarning) {
    const msg = buildMessage(success, failed, skipped, entityLabel);
    displayWarningSnackbar(msg);
    return { shown: true, kind: 'warning', message: msg };
  }

  // Rien à afficher (ex: formats atypiques)
  return { shown: false, kind: 'none' };
}

export default {
  notifyCSVImportOutcome
};
