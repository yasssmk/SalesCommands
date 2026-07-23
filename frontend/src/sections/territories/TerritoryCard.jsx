// frontend/src/sections/territories/TerritoryCard.jsx

import PropTypes from 'prop-types';
import { useRouter } from 'next/navigation';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

// icons
import BankOutlined from '@ant-design/icons/BankOutlined';
import ContactsOutlined from '@ant-design/icons/ContactsOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';

// api / utils
import { TERRITORY_TYPES } from 'api/territories/territories';
import { goalGradient } from 'sections/home/utils/goalGradient';
import { formatDateOnly } from 'config/formatters';

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
  count = null,
  loading = false,
  onDelete,
  // Selection props
  selected = false,
  onSelect,
  selectionMode = false
}) {
  const router = useRouter();
  const theme = useTheme();

  const isAccountType = territory.type === TERRITORY_TYPES.ACCOUNT;

  // Count now arrives pre-computed from the list's batched POST /territories/counts/
  // (one round-trip for the whole visible page), so the per-card workspace N+1
  // is gone. The backend already returns accounts vs contacts by territory type.
  const displayCount = count ?? 0;
  const displayLoading = loading;

  // Coverage snapshot (materialised on the row; may be absent until first
  // computed). Framed as a work queue — "N to go", never "0% done" — via the
  // shared goalGradient (framing:'queue'), the same vocab the Home block uses.
  const hasCoverage =
    territory.coverage_computed_at != null &&
    territory.coverage_denominator != null;
  const coverage = hasCoverage
    ? goalGradient(
        territory.coverage_numerator,
        territory.coverage_denominator,
        { framing: 'queue', noun: isAccountType ? 'accounts' : 'contacts' }
      )
    : null;

  const ownerName = territory.owner?.full_name;
  const teamName = territory.team?.name;

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


   const handleDelete = (e) => {
    e.stopPropagation();
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
        borderColor: selected ? 'error.main' : 'divider',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 0.2s ease-in-out',
        cursor: selectionMode ? 'default' : 'pointer',
        bgcolor: selected ? 'error.lighter' : 'background.paper',
        '&:hover': {
          borderColor: selectionMode ? 'divider' : 'primary.main',
          boxShadow: selectionMode ? 'none' : '0 4px 12px rgba(0,0,0,0.08)'
        },
        '&:hover .gtm-card-delete': { opacity: 1 },
        '&:active': {
          transform: selectionMode ? 'none' : 'scale(0.99)'
        }
      }}
    >
      <CardContent sx={{ flexGrow: 1 }}>
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
              <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.5 }}>
                {/* Type chip: both secondary, Account = dark (filled), Contact =
                    light (variant="light", the template's soft variant used by
                    the System chip below). */}
                <Chip
                  label={isAccountType ? 'Accounts' : 'Contacts'}
                  size="small"
                  color="secondary"
                  variant={isAccountType ? 'filled' : 'light'}
                  sx={{ height: 20, fontSize: '0.7rem' }}
                />
                {/* Distinct 'info' chip, only when the territory is targeted by
                    an ACTIVE campaign. info (not primary) so it never competes
                    with the primary.main hover-border affordance. No chip is
                    shown for the "not in a campaign" case. */}
                {territory.is_in_active_campaign && (
                  <Chip
                    label="In campaign"
                    size="small"
                    color="info"
                    sx={{ height: 20, fontSize: '0.7rem' }}
                  />
                )}
              </Stack>
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

        {/* Count — horizontal row, mirroring the campaign card's big count
            (Stack direction="row" spacing={1} alignItems="baseline") for visual
            homogeneity across card families. */}
        <Box sx={{ mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="baseline">
            <Typography variant="h2" component="div" fontWeight={600}>
              {displayLoading ? '...' : displayCount}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {isAccountType
                ? (displayCount === 1 ? 'account' : 'accounts')
                : (displayCount === 1 ? 'contact' : 'contacts')}
            </Typography>
          </Stack>
        </Box>

        {/* Coverage — queue-framed ("N to go"), never "0% done". Same thin bar
            visual as the campaign card. Hidden entirely until a snapshot exists. */}
        {coverage && (
          <Box sx={{ mb: 2 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={0.5}>
              <Typography variant="caption" color="text.secondary">
                Coverage
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {coverage.headline}
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={coverage.pct}
              sx={{
                height: 6,
                borderRadius: 3,
                bgcolor: theme.palette.grey[200],
                '& .MuiLinearProgress-bar': { borderRadius: 3 }
              }}
            />
          </Box>
        )}

        {/* Filter summary */}
        <Typography variant="caption" color="text.secondary" component="div">
          {filterSummary()}
        </Typography>

        {/* Attribution — owner + team (mirrors the campaign card). */}
        {ownerName && (
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1.5 }}>
            <UserOutlined style={{ fontSize: 12, color: theme.palette.text.secondary }} />
            <Typography variant="caption" color="text.secondary" noWrap>
              {ownerName}
              {teamName ? ` — ${teamName}` : ''}
            </Typography>
          </Stack>
        )}
        {!ownerName && teamName && (
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1.5 }}>
            <TeamOutlined style={{ fontSize: 12, color: theme.palette.text.secondary }} />
            <Typography variant="caption" color="text.secondary" noWrap>
              {teamName}
            </Typography>
          </Stack>
        )}

        {/* Created — low-key at the bottom (present for the sort, not a CTA). */}
        {territory.created_at && (
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1 }}>
            <ClockCircleOutlined style={{ fontSize: 12, color: theme.palette.text.disabled }} />
            <Typography variant="caption" color="text.disabled">
              Created {formatDateOnly(territory.created_at)}
            </Typography>
          </Stack>
        )}
      </CardContent>

      {/* Top-right corner — exclusive state machine (non-protected cards only):
          exactly one element at a time. Selection mode shows the checkbox;
          otherwise the individual delete reveals on hover. System territories
          are protected: they never show a checkbox or delete here, and their
          status ("System" chip) stays in the header in every state. */}
      {!territory.is_system && (
        selectionMode ? (
          <Box sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1 }}>
            <Checkbox
              checked={selected}
              onChange={handleSelect}
              onClick={(e) => e.stopPropagation()}
              size="small"
              sx={{
                bgcolor: 'background.paper',
                borderRadius: 1,
                '&:hover': { bgcolor: 'background.paper' }
              }}
            />
          </Box>
        ) : (
          <Box
            className="gtm-card-delete"
            sx={{
              position: 'absolute',
              top: 8,
              right: 8,
              zIndex: 1,
              opacity: 0,
              transition: 'opacity 0.2s ease-in-out'
            }}
          >
            <Tooltip title="Delete">
              <IconButton
                size="small"
                color="error"
                onClick={handleDelete}
                sx={{ bgcolor: 'error.lighter', '&:hover': { bgcolor: 'error.light' } }}
              >
                <DeleteOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </Box>
        )
      )}
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
    filter_definition: PropTypes.object,
    is_in_active_campaign: PropTypes.bool,
    coverage_numerator: PropTypes.number,
    coverage_denominator: PropTypes.number,
    coverage_computed_at: PropTypes.string,
    owner: PropTypes.shape({ full_name: PropTypes.string }),
    team: PropTypes.shape({ name: PropTypes.string }),
    created_at: PropTypes.string
  }).isRequired,
  count: PropTypes.number,
  loading: PropTypes.bool,
  onDelete: PropTypes.func,
  // Selection props
  selected: PropTypes.bool,
  onSelect: PropTypes.func,
  selectionMode: PropTypes.bool
};