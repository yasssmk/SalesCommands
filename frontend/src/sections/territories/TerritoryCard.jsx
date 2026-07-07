// frontend/src/sections/territories/TerritoryCard.jsx

import PropTypes from 'prop-types';
import { useRouter } from 'next/navigation';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// icons
import BankOutlined from '@ant-design/icons/BankOutlined';
import ContactsOutlined from '@ant-design/icons/ContactsOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import CopyOutlined from '@ant-design/icons/CopyOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import ArrowRightOutlined from '@ant-design/icons/ArrowRightOutlined';

// api
import { TERRITORY_TYPES, useGetTerritoryWorkspace } from 'api/territories/territories';

// ==============================|| TERRITORY CARD ||============================== //

/**
 * Territory Card Component
 * 
 * Displays a territory as a card with:
 * - Name and description
 * - Type indicator (Account/Contact)
 * - Count of records
 * - Filter summary
 * - Action buttons
 */
export default function TerritoryCard({ 
  territory, 
  accountsCount = 0,
  loading = false,
  onEdit,
  onDelete,
  // Selection props
  selected = false,
  onSelect,
  selectionMode = false
}) {
  const router = useRouter();

  const isAccountType = territory.type === TERRITORY_TYPES.ACCOUNT;
  const isContactType = territory.type === TERRITORY_TYPES.CONTACT;

  // Contact territories derive their count from the scope-aware workspace
  // stats endpoint. Account territories keep the count passed by the list.
  // The hook is keyed null (no fetch) for account territories.
  const { stats: contactStats, loading: contactCountLoading } =
    useGetTerritoryWorkspace(isContactType ? territory.id : null);

  const displayCount = isContactType
    ? contactStats?.contacts_count ?? 0
    : accountsCount;
  const displayLoading = isContactType ? contactCountLoading : loading;

  // ==============================|| HANDLERS ||============================== //

  /**
   * Navigate to Accounts page with filters from territory
   */
  /**
 * Navigate to Accounts page with territory filter
 */
  const handleExploreAccounts = () => {
    const params = new URLSearchParams();
    
    // Pass territory_id - backend will apply filter_definition
    params.set('territory_id', territory.id);
    params.set('page', '1');
    
    const url = `/businessData/accounts?${params.toString()}`;
    
    router.push(url);
  };

  /**
   * Navigate to Contacts page (future)
   */
  const handleExploreContacts = () => {
    // Future: navigate to /admin/contacts with filters
    console.log('Contacts page coming soon');
  };

  /**
   * Navigate to Territory Workspace
   */
  const handleCardClick = () => {
    // Don't navigate if in selection mode
    if (selectionMode) return;
    
    // Navigate to territory workspace (both Account and Contact types)
    router.push(`/territories/${territory.id}`);
  };


  const handleEdit = () => {
    if (onEdit) {
      onEdit(territory);
    }
  };

   const handleDelete = () => {
    if (onDelete) {
      onDelete(territory);
    }
  };

  const handleSelect = (event) => {
    event.stopPropagation();
    if (onSelect) {
      onSelect(territory.id);
    }
  };

  // ==============================|| FILTER SUMMARY ||============================== //

    const filterSummary = () => {
    if (!territory.filter_definition || Object.keys(territory.filter_definition).length === 0) {
      return 'No filters applied';
    }

    const parts = [];
    
    const formatFilterValue = (label, value) => {
      if (!value) return null;
      if (Array.isArray(value)) {
        if (value.length === 0) return null;
        if (value.length === 1) return `${label}: ${value[0]}`;
        return `${label}: ${value.length} selected`;
      }
      return `${label}: ${value}`;
    };
    
    // Account filters
    const typeFilter = formatFilterValue('Type', territory.filter_definition.type);
    if (typeFilter) parts.push(typeFilter);
    
    const classificationFilter = formatFilterValue('Classification', territory.filter_definition.classification);
    if (classificationFilter) parts.push(classificationFilter);
    
    const industryFilter = formatFilterValue('Industry', territory.filter_definition.industry);
    if (industryFilter) parts.push(industryFilter);
    
    const countryFilter = formatFilterValue('Country', territory.filter_definition.country);
    if (countryFilter) parts.push(countryFilter);
    
    // Contact filters
    const influenceFilter = formatFilterValue('Influence', territory.filter_definition.influence_level);
    if (influenceFilter) parts.push(influenceFilter);
    
    const departmentFilter = formatFilterValue('Department', territory.filter_definition.standard_department);
    if (departmentFilter) parts.push(departmentFilter);
    
    if (territory.filter_definition.has_buying_authority !== undefined) {
      parts.push(`Buying Authority: ${territory.filter_definition.has_buying_authority ? 'Yes' : 'No'}`);
    }
    
    // Owner scope (account or contact)
    const accountScope = territory.filter_definition.account_scope;
    const contactScope = territory.filter_definition.contact_scope;
    const scope = accountScope || contactScope;
    
    if (scope) {
      const scopeLabels = {
        'mine': 'Owner: Mine',
        'team': 'Owner: My Team'
      };
      parts.push(scopeLabels[scope] || `Owner: ${scope}`);
    } else if (territory.filter_definition.account_owner) {
      parts.push('Owner: Specific user');
    }

    return parts.length > 0 ? parts.join(' · ') : 'No filters applied';
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Card 
      elevation={0}
      onClick={handleCardClick}
      sx={{ 
        position: 'relative',
        border: '1px solid',
        borderColor: selected ? 'primary.main' : 'divider',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 0.2s ease-in-out',
        cursor: selectionMode ? 'default' : 'pointer',
        bgcolor: selected ? 'primary.lighter' : 'background.paper',
        '&:hover': {
          borderColor: selectionMode ? 'divider' : 'primary.main',
          boxShadow: selectionMode ? 'none' : '0 4px 12px rgba(0,0,0,0.08)'
        },
        '&:active': {
          transform: selectionMode ? 'none' : 'scale(0.99)'
        }
      }}
    >
      <CardContent sx={{ flexGrow: 1 }}>
        {/* Selection Checkbox */}
        {selectionMode && (
          <Box sx={{ position: 'absolute', top: 8, left: 8, zIndex: 1 }}>
            <Checkbox
              checked={selected}
              onChange={handleSelect}
              onClick={(e) => e.stopPropagation()}
              disabled={territory.is_system}
              size="small"
              sx={{
                bgcolor: 'background.paper',
                borderRadius: 1,
                '&:hover': { bgcolor: 'background.paper' }
              }}
            />
          </Box>
        )}

        {/* Header */}
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" mb={2}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            {/* Type Icon */}
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: 1,
                bgcolor: isAccountType ? 'primary.lighter' : 'secondary.lighter',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              {isAccountType ? (
                <BankOutlined style={{ fontSize: 20, color: 'inherit' }} />
              ) : (
                <ContactsOutlined style={{ fontSize: 20, color: 'inherit' }} />
              )}
            </Box>

            {/* Name */}
            <Box>
              <Typography variant="h5" fontWeight={600}>
                {territory.name}
              </Typography>
              <Chip 
                label={isAccountType ? 'Accounts' : 'Contacts'} 
                size="small" 
                color={isAccountType ? 'primary' : 'secondary'}
                variant="outlined"
                sx={{ mt: 0.5, height: 20, fontSize: '0.7rem' }}
              />
            </Box>
          </Stack>

          {/* Built-in badge */}
          {territory.is_system && (
            <Chip 
              label="System" 
              size="small" 
              variant="light"
              color="default"
            />
          )}
        </Stack>

        {/* Description */}
        {territory.description && (
          <Typography variant="body2" color="text.secondary" mb={2}>
            {territory.description}
          </Typography>
        )}

        {/* Count */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="h2" component="div" fontWeight={600}>
            {displayLoading ? '...' : displayCount}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {isAccountType ? 'accounts' : 'contacts'}
          </Typography>
        </Box>

        {/* Filter summary */}
        <Typography variant="caption" color="text.secondary">
          {filterSummary()}
        </Typography>
      </CardContent>

      <Divider />

      {/* Actions */}
      <CardActions sx={{ justifyContent: 'flex-end', px: 2, py: 1.5 }}>
      {/* Action icons */}
      <Stack direction="row" spacing={0}>
        <Tooltip title={territory.is_system ? "Edit (limited)" : "Edit"}>
          <span>
            <IconButton 
              size="small" 
              onClick={handleEdit}
            >
              <EditOutlined style={{ fontSize: 16 }} />
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip title={territory.is_system ? "Cannot delete system territory" : "Delete"}>
          <span>
            <IconButton 
              size="small" 
              onClick={handleDelete}
              disabled={territory.is_system}
            >
              <DeleteOutlined style={{ fontSize: 16 }} />
            </IconButton>
          </span>
        </Tooltip>
      </Stack>
    </CardActions>
    </Card>
  );
}

// ==============================|| PROP TYPES ||============================== //

TerritoryCard.propTypes = {
  territory: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    type: PropTypes.oneOf(['ACCOUNT', 'CONTACT']).isRequired,
    description: PropTypes.string,
    is_system: PropTypes.bool,
    filter_definition: PropTypes.object
  }).isRequired,
  accountsCount: PropTypes.number,
  loading: PropTypes.bool,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
  // Selection props
  selected: PropTypes.bool,
  onSelect: PropTypes.func,
  selectionMode: PropTypes.bool
};