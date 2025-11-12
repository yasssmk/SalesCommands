// frontend/src/sections/admin/roles/PermissionsMatrix.jsx

import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';

// ant design icons
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';

// project imports
import { PERMISSIONS_REGISTRY, MODULES, ACTIONS, getScope, getScopeLabel } from './permissionsRegistry';

/**
 * PermissionsMatrix Component
 * 
 * Displays a comprehensive permissions matrix for a given tier.
 * Shows all modules (rows) x all CRUD actions (columns) with scope indicators.
 * 
 * Scope indicators:
 * - client (All): Green checkmark - Full tenant access
 * - team (Team): Orange group icon - Team-limited access
 * - mine (Mine): Blue person icon - Personal access only
 * - none (None): Red cancel icon - No access
 * 
 * @component
 * @example
 * <PermissionsMatrix tier="admin" />
 * <PermissionsMatrix tier="manager" showLegend={false} />
 */
function PermissionsMatrix({ tier, showLegend = true, compact = false }) {
  
  // ==============================|| SCOPE CONFIGURATION ||============================== //
  
  /**
   * Get visual configuration for a scope value
   */
  const getScopeConfig = (scope) => {
    const configs = {
      client: {
        label: 'All',
        color: 'success',
        icon: CheckCircleOutlined,
        description: 'Full access to all tenant data'
      },
      team: {
        label: 'Team',
        color: 'warning',
        icon: TeamOutlined,
        description: 'Access limited to team data'
      },
      mine: {
        label: 'Mine',
        color: 'info',
        icon: UserOutlined,
        description: 'Access to personal data only'
      },
      none: {
        label: 'None',
        color: 'error',
        icon: CloseCircleOutlined,
        description: 'No access'
      }
    };

    return configs[scope] || configs.none;
  };

  // ==============================|| SCOPE CELL RENDERER ||============================== //
  
  /**
   * Render a scope cell with icon and label
   */
  const ScopeCell = ({ scope }) => {
    const config = getScopeConfig(scope);
    const IconComponent = config.icon;

    if (compact) {
      return (
        <Chip
          icon={<IconComponent />}
          label={config.label}
          color={config.color}
          size="small"
          variant="outlined"
          sx={{ minWidth: 80 }}
        />
      );
    }

    return (
      <Stack direction="row" spacing={1} alignItems="center" justifyContent="center" sx={{ width: '100%' }}>
        <IconComponent 
          fontSize="small" 
          color={config.color}
          sx={{ opacity: 0.8 }}
        />
        <Typography variant="body2" color="text.secondary">
          {config.label}
        </Typography>
      </Stack>
    );
  };

  ScopeCell.propTypes = {
    scope: PropTypes.oneOf(['client', 'team', 'mine', 'none']).isRequired
  };

  // ==============================|| FORMAT MODULE NAME ||============================== //
  
  /**
   * Capitalize and format module name for display
   */
  const formatModuleName = (module) => {
    return module.charAt(0).toUpperCase() + module.slice(1);
  };

  /**
   * Format action name for display
   */
  const formatActionName = (action) => {
    return action.charAt(0).toUpperCase() + action.slice(1);
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      <TableContainer component={Paper} variant="outlined">
        <Table size={compact ? 'small' : 'medium'}>
          {/* Header */}
          <TableHead>
            <TableRow>
              <TableCell>
                <Typography variant="subtitle2" fontWeight={600}>
                  Module
                </Typography>
              </TableCell>
              {ACTIONS.map((action) => (
                <TableCell key={action} align="center">
                  <Typography variant="subtitle2" fontWeight={600}>
                    {formatActionName(action)}
                  </Typography>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>

          {/* Body */}
          <TableBody>
            {MODULES.map((module) => (
              <TableRow 
                key={module}
                hover
                sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
              >
                <TableCell component="th" scope="row" >
                  <Typography variant="body2" fontWeight={500}>
                    {formatModuleName(module)}
                  </Typography>
                </TableCell>
                {ACTIONS.map((action) => {
                  const scope = getScope(module, action, tier);
                  return (
                    <TableCell key={action} align="center">
                      <ScopeCell scope={scope}  />
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Legend */}
      {showLegend && (
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            Permission Scopes Legend
          </Typography>
          <Stack direction="row" spacing={3} flexWrap="wrap">
            {['client', 'team', 'mine', 'none'].map((scope) => {
              const config = getScopeConfig(scope);
              const IconComponent = config.icon;
              return (
                <Stack key={scope} direction="row" spacing={0.5} alignItems="center">
                  <IconComponent 
                    fontSize="small" 
                    color={config.color}
                    sx={{ opacity: 0.8 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    <strong>{config.label}:</strong> {config.description}
                  </Typography>
                </Stack>
              );
            })}
          </Stack>
        </Box>
      )}
    </Box>
  );
}

PermissionsMatrix.propTypes = {
  /**
   * The tier level to display permissions for
   * @type {'admin' | 'manager' | 'individual'}
   */
  tier: PropTypes.oneOf(['admin', 'manager', 'individual']).isRequired,
  
  /**
   * Whether to show the legend explaining scopes
   */
  showLegend: PropTypes.bool,
  
  /**
   * Compact mode with smaller cells and chips
   */
  compact: PropTypes.bool
};

export default PermissionsMatrix;