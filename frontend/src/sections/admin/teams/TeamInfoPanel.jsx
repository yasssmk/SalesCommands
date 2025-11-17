// frontend/src/sections/admin/teams/TeamInfoPanel.jsx

import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import MainCard from 'components/MainCard';

// icons
import { EditOutlined, DeleteOutlined, TeamOutlined } from '@ant-design/icons';

// utils
import { formatDateTime } from 'config/formatters';

/**
 * TeamInfoPanel - Affiche les détails d'une team sélectionnée
 */
function TeamInfoPanel({ team, onEdit, onDelete }) {
  
  // ==================== EMPTY STATE ====================
  
  if (!team) {
    return (
      <MainCard
        title="Team Details"
        content={false}
        sx={{ height: '100%', minHeight: 400 }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: 400,
            p: 3
          }}
        >
          <TeamOutlined style={{ fontSize: 48, color: '#bdbdbd', marginBottom: 16 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            Select a team
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center">
            Click on a team in the tree view to see its details
          </Typography>
        </Box>
      </MainCard>
    );
  }

  // ==================== TEAM DETAILS ====================

  return (
    <MainCard
      title="Team Details"
      content={false}
      sx={{ height: '100%', minHeight: 400 }}
    >
      <Box sx={{ p: 2.5 }}>
        <Grid container spacing={2.5}>
          
          {/* Team Name */}
          <Grid item xs={12}>
            <Typography variant="caption" color="text.secondary">
              Team Name
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="h6">
                {team.name}
              </Typography>
              {team.children && team.children.length > 0 && (
                <Chip 
                  label={`${team.children.length} sub-team${team.children.length > 1 ? 's' : ''}`}
                  size="small" 
                  color="primary"
                  variant="light"
                />
              )}
            </Stack>
          </Grid>

          {/* Description */}
          {team.description && (
            <Grid item xs={12}>
              <Typography variant="caption" color="text.secondary">
                Description
              </Typography>
              <Typography variant="body2" color="text.primary">
                {team.description}
              </Typography>
            </Grid>
          )}

          {/* Manager */}
          <Grid item xs={12}>
            <Typography variant="caption" color="text.secondary">
              Manager
            </Typography>
            {team.manager ? (
              <Stack spacing={0.5}>
                <Typography variant="h6">
                  {team.manager.first_name} {team.manager.last_name}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {team.manager.email}
                </Typography>
              </Stack>
            ) : (
              <Typography variant="h6" color="text.disabled">
                No Manager
              </Typography>
            )}
          </Grid>

          {/* Parent Team */}
          <Grid item xs={12}>
            <Typography variant="caption" color="text.secondary">
              Parent Team
            </Typography>
            <Typography variant="h6" color={team.parent ? 'text.primary' : 'text.disabled'}>
              {team.parent ? 'Has Parent' : 'No Parent (Root Team)'}
            </Typography>
          </Grid>

          {/* Member Count */}
          <Grid item xs={12}>
            <Typography variant="caption" color="text.secondary">
              Team Members
            </Typography>
            <Typography variant="h6">
              {team.member_count || 0} member{team.member_count !== 1 ? 's' : ''}
            </Typography>
          </Grid>

          {/* Created Date */}
          {team.created_at && (
            <Grid item xs={12}>
              <Typography variant="caption" color="text.secondary">
                Created
              </Typography>
              <Typography variant="body2" color="text.primary">
                {formatDateTime(team.created_at)}
              </Typography>
            </Grid>
          )}

          {/* Actions */}
          <Grid item xs={12}>
            <Divider sx={{ my: 1 }} />
            <Stack direction="row" spacing={1}>
              <Button
                variant="outlined"
                startIcon={<EditOutlined />}
                onClick={() => onEdit && onEdit(team)}
              >
                Edit
              </Button>
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteOutlined />}
                onClick={() => onDelete && onDelete(team)}
              >
                Delete
              </Button>
            </Stack>
          </Grid>
          
        </Grid>
      </Box>
    </MainCard>
  );
}

TeamInfoPanel.propTypes = {
  team: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    description: PropTypes.string,
    manager: PropTypes.shape({
      id: PropTypes.string,
      first_name: PropTypes.string,
      last_name: PropTypes.string,
      email: PropTypes.string
    }),
    parent: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    member_count: PropTypes.number,
    created_at: PropTypes.string,
    children: PropTypes.array
  }),
  onEdit: PropTypes.func,
  onDelete: PropTypes.func
};

export default TeamInfoPanel;