// frontend/src/components/bulk/BulkOperationSyncDialog.jsx

import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import Avatar from 'components/@extended/Avatar';

// assets
import SyncOutlined from '@ant-design/icons/SyncOutlined';

import pollOperationStatus from 'utils/pollOperationStatus';

/**
 * ✅ COMPOSANT RÉUTILISABLE - AFFICHAGE DU SYNC APRÈS BULK TIMEOUT
 * 
 * Composant standardisé pour afficher l'état de synchronisation
 * pendant qu'une opération bulk continue à s'exécuter en arrière-plan.
 * 
 * **Usage :**
 * Utilisé dans TOUS les composants bulk (delete, update, create)
 * pour afficher un feedback cohérent pendant le polling.
 * 
 * **Design :**
 * - Avatar avec icône SyncOutlined animée
 * - CircularProgress pour indiquer l'attente
 * - Messages clairs sur l'état du sync
 * - Numéro de tentative affiché
 * 
 * @example
 * // Dans AlertUserBulkDelete ou FormUserBulkEdit
 * {syncing ? (
 *   <BulkOperationSyncDialog 
 *     attempt={syncAttempt}
 *     maxAttempts={3}
 *     operation="delete"
 *   />
 * ) : (
 *   <NormalContent />
 * )}
 * 
 * @param {number} attempt - Numéro de la tentative en cours (1, 2, 3...)
 * @param {number} maxAttempts - Nombre maximum de tentatives (défaut: 3)
 * @param {string} operation - Type d'opération ('delete', 'update', 'create')
 * @param {Object} sx - Styles MUI supplémentaires
 */
export default function BulkOperationSyncDialog({ 
  attempt = 1, 
  maxAttempts = pollOperationStatus.config.maxAttempts,
  operation = 'update',
  sx = {}
}) {
  
  // Messages personnalisés selon l'opération
  const operationMessages = {
    delete: {
      title: 'Deleting data...',
      message: 'Waiting for server to finish deleting...'
    },
    update: {
      title: 'Updating data...',
      message: 'Waiting for server to finish updating...'
    },
    create: {
      title: 'Creating data...',
      message: 'Waiting for server to finish creating...'
    }
  };

  const messages = operationMessages[operation] || operationMessages.update;

  return (
    <Box sx={{ p: 5, ...sx }}>
      <Stack alignItems="center" spacing={3}>
        {/* Avatar avec icône animée */}
        <Avatar 
          color="primary" 
          sx={{ width: 72, height: 72, fontSize: '1.75rem' }}
        >
          <SyncOutlined spin />
        </Avatar>
        
        {/* Titre et messages */}
        <Stack spacing={2} alignItems="center" sx={{ width: 1 }}>
          <Typography variant="h4" align="center">
            Syncing data...
          </Typography>
          
          <Stack spacing={1.5} alignItems="center">
            <CircularProgress size={24} />
            
            <Typography align="center" color="text.secondary">
              {messages.message}
            </Typography>
            
            <Typography variant="caption" align="center" color="text.secondary">
              Attempt {attempt} of {maxAttempts} - Please be patient.
            </Typography>
          </Stack>
        </Stack>
      </Stack>
    </Box>
  );
}

BulkOperationSyncDialog.propTypes = {
  attempt: PropTypes.number,
  maxAttempts: PropTypes.number,
  operation: PropTypes.oneOf(['delete', 'update', 'create']),
  sx: PropTypes.object
};