// frontend/src/hooks/useBulkOperationSync.js

import { useState, useEffect, useCallback } from 'react';

/**
 * ✅ HOOK RÉUTILISABLE - GESTION DU SYNC APRÈS BULK TIMEOUT
 * 
 * Centralise toute la logique de synchronisation après qu'une opération bulk
 * ait timeout côté client mais continue à s'exécuter côté backend.
 * 
 * **Problème résolu :**
 * - Client timeout 20s → Backend continue à traiter
 * - Polling progressif pour laisser le temps au backend de finir
 * - UI affiche un état "Syncing..." pendant le polling
 * - Fermeture automatique une fois le sync terminé
 * 
 * **Features :**
 * - États `syncing` et `syncAttempt` pour l'UI
 * - Callbacks `onSyncProgress` et `onSyncComplete` pour l'API
 * - Effet de fermeture automatique avec délai configurable
 * - Fonction `resetSync()` pour réinitialiser les états
 * 
 * **Usage dans n'importe quel composant bulk :**
 * 
 * @example
 * // Dans AlertUserBulkDelete, FormUserBulkEdit, etc.
 * function MyBulkComponent({ onClose, selectedIds }) {
 *   const [submitting, setSubmitting] = useState(false);
 *   
 *   const { 
 *     syncing, 
 *     syncAttempt, 
 *     onSyncProgress, 
 *     onSyncComplete,
 *     resetSync 
 *   } = useBulkOperationSync({
 *     onComplete: () => {
 *       onClose?.();
 *       // Autres actions après fermeture
 *     },
 *     closeDelay: 300  // Délai avant fermeture (ms)
 *   });
 * 
 *   const handleBulkAction = async () => {
 *     setSubmitting(true);
 *     
 *     const result = await bulkDeleteUsers(
 *       selectedIds, 
 *       'partial',
 *       onSyncProgress,   // Callback intermédiaire
 *       onSyncComplete    // Callback de fin
 *     );
 *     
 *     setSubmitting(false);
 *   };
 * 
 *   return (
 *     <Dialog open={open}>
 *       {syncing ? (
 *         <SyncingView attempt={syncAttempt} />
 *       ) : (
 *         <NormalView />
 *       )}
 *     </Dialog>
 *   );
 * }
 * 
 * @param {Object} options - Options de configuration
 * @param {Function} options.onComplete - Callback appelé après sync terminé (ex: fermer modal)
 * @param {number} options.closeDelay - Délai en ms avant d'appeler onComplete (défaut: 300)
 * @param {boolean} options.autoClose - Si false, n'appelle pas onComplete automatiquement (défaut: true)
 * 
 * @returns {Object} API du hook
 * @returns {boolean} returns.syncing - État actuel du sync (true pendant polling)
 * @returns {number} returns.syncAttempt - Numéro de la tentative en cours (1, 2, 3...)
 * @returns {Function} returns.onSyncProgress - Callback à passer à l'API (attempt, maxAttempts) => void
 * @returns {Function} returns.onSyncComplete - Callback à passer à l'API () => void
 * @returns {Function} returns.resetSync - Fonction pour réinitialiser les états
 */
export function useBulkOperationSync(options = {}) {
  const {
    onComplete = null,
    closeDelay = 300,
    autoClose = true
  } = options;

  // ==============================|| ÉTATS ||============================== //
  
  const [syncing, setSyncing] = useState(false);
  const [syncAttempt, setSyncAttempt] = useState(0);

  // ==============================|| CALLBACKS ||============================== //

  /**
   * Callback pour notifier les tentatives de sync (état intermédiaire)
   * Appelé par refetchAfterBulkTimeout() à chaque tentative
   */
  const onSyncProgress = useCallback((attempt, maxAttempts) => {
    console.log(`[useBulkOperationSync] Sync progress: ${attempt}/${maxAttempts}`);
    setSyncing(true);
    setSyncAttempt(attempt);
  }, []);

  /**
   * Callback pour notifier la FIN du sync (état final)
   * Appelé par refetchAfterBulkTimeout() après la dernière tentative
   */
  const onSyncComplete = useCallback(() => {
    console.log('[useBulkOperationSync] Sync completed, stopping sync indicator');
    setSyncing(false);
  }, []);

  /**
   * Fonction pour réinitialiser manuellement les états
   * Utile si le composant doit rester ouvert après une action
   */
  const resetSync = useCallback(() => {
    console.log('[useBulkOperationSync] Manual reset');
    setSyncing(false);
    setSyncAttempt(0);
  }, []);

  // ==============================|| EFFET DE FERMETURE ||============================== //

  /**
   * Effet : Fermer automatiquement après sync terminé
   * 
   * Se déclenche quand :
   * - syncing passe à false (sync terminé)
   * - ET syncAttempt > 0 (au moins une tentative a été faite)
   * - ET autoClose === true
   */
  useEffect(() => {
    if (!syncing && syncAttempt > 0 && autoClose) {
      console.log(`[useBulkOperationSync] Sync completed, calling onComplete after ${closeDelay}ms`);
      
      const timer = setTimeout(() => {
        if (onComplete && typeof onComplete === 'function') {
          try {
            onComplete();
          } catch (err) {
            console.error('[useBulkOperationSync] onComplete callback error:', err);
          }
        }
      }, closeDelay);

      return () => clearTimeout(timer);
    }
  }, [syncing, syncAttempt, autoClose, closeDelay, onComplete]);

  // ==============================|| RETURN API ||============================== //

  return {
    // États pour l'UI
    syncing,
    syncAttempt,
    
    // Callbacks pour l'API
    onSyncProgress,
    onSyncComplete,
    
    // Utilitaires
    resetSync
  };
}

// ==============================|| EXEMPLES D'USAGE ||============================== //

/**
 * EXEMPLE 1 : Modal de confirmation (AlertUserBulkDelete)
 * 
 * function AlertUserBulkDelete({ open, handleClose, selectedIds }) {
 *   const [deleting, setDeleting] = useState(false);
 *   
 *   const { syncing, syncAttempt, onSyncProgress, onSyncComplete } = useBulkOperationSync({
 *     onComplete: () => {
 *       handleClose?.();
 *       onDeleteComplete?.();
 *     }
 *   });
 * 
 *   const handleDelete = async () => {
 *     setDeleting(true);
 *     const res = await bulkDeleteUsers(selectedIds, 'partial', onSyncProgress, onSyncComplete);
 *     setDeleting(false);
 *   };
 * 
 *   return (
 *     <Dialog open={open} onClose={syncing ? undefined : handleClose}>
 *       {syncing ? (
 *         <SyncingView attempt={syncAttempt} />
 *       ) : (
 *         <ConfirmView onConfirm={handleDelete} deleting={deleting} />
 *       )}
 *     </Dialog>
 *   );
 * }
 */

/**
 * EXEMPLE 2 : Formulaire (FormUserBulkEdit)
 * 
 * function FormUserBulkEdit({ closeModal, selectedIds }) {
 *   const { syncing, syncAttempt, onSyncProgress, onSyncComplete } = useBulkOperationSync({
 *     onComplete: () => {
 *       closeModal?.();
 *     }
 *   });
 * 
 *   const formik = useFormik({
 *     onSubmit: async (values, { setSubmitting }) => {
 *       const patch = buildPatchPayload(values);
 *       const result = await bulkUpdateUsers(selectedIds, patch, 'partial', onSyncProgress, onSyncComplete);
 *       setSubmitting(false);
 *     }
 *   });
 * 
 *   return (
 *     <Form onSubmit={formik.handleSubmit}>
 *       {syncing ? (
 *         <SyncingView attempt={syncAttempt} />
 *       ) : (
 *         <FormFields />
 *       )}
 *     </Form>
 *   );
 * }
 */

/**
 * EXEMPLE 3 : Sans fermeture automatique (snackbar seulement)
 * 
 * function BulkActionButton({ selectedIds }) {
 *   const { onSyncProgress, onSyncComplete, resetSync } = useBulkOperationSync({
 *     autoClose: false  // Pas de fermeture automatique
 *   });
 * 
 *   const handleAction = async () => {
 *     const result = await bulkUpdateUsers(selectedIds, patch, 'partial', onSyncProgress, onSyncComplete);
 *     
 *     if (result.success) {
 *       openSnackbar({ message: 'Success!' });
 *       resetSync();  // Reset manuel
 *     }
 *   };
 * }
 */

export default useBulkOperationSync;