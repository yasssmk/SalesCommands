// frontend/src/sections/territories/TerritoryCard.jsx

import PropTypes from 'prop-types';
import { useRouter } from 'next/navigation';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
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
import { TERRITORY_TYPES } from 'api/territories';

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
  loading = false 
}) {
  const router = useRouter();

  const isAccountType = territory.type === TERRITORY_TYPES.ACCOUNT;
  const isContactType = territory.type === TERRITORY_TYPES.CONTACT;

  // ==============================|| HANDLERS ||============================== //

  /**
   * Navigate to Accounts page with filters from territory
   */
  const handleExploreAccounts = () => {
    const params = new URLSearchParams();
    
    // Apply territory filters to URL params
    if (territory.filters) {
      Object.entries(territory.filters).forEach(([key, value]) => {
        if (value) {
          params.set(key, value);
        }
      });
    }
    
    params.set('page', '1');
    
    const queryString = params.toString();
    const url = queryString ? `/admin/accounts?${queryString}` : '/admin/accounts';
    
    router.push(url);
  };

  /**
   * Navigate to Contacts page (future)
   */
  const handleExploreContacts = () => {
    // Future: navigate to /admin/contacts with filters
    console.log('Contacts page coming soon');
  };

  const handleEdit = () => {
    // Future: open edit modal
    console.log('Edit territory:', territory.id);
  };

  const handleDuplicate = () => {
    // Future: duplicate territory
    console.log('Duplicate territory:', territory.id);
  };

  const handleDelete = () => {
    // Future: delete territory
    console.log('Delete territory:', territory.id);
  };

  // ==============================|| FILTER SUMMARY ||============================== //

  const filterSummary = () => {
    if (!territory.filters || Object.keys(territory.filters).length === 0) {
      return 'No filters applied';
    }

    const parts = [];
    if (territory.filters.type) {
      parts.push(`Type: ${territory.filters.type}`);
    }
    if (territory.filters.classification) {
      parts.push(`Classification: ${territory.filters.classification}`);
    }
    if (territory.filters.account_owner) {
      parts.push('Owner: Filtered');
    }

    return parts.length > 0 ? parts.join(' · ') : 'No filters applied';
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Card 
      elevation={0}
      sx={{ 
        border: '1px solid',
        borderColor: 'divider',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        transition: 'box-shadow 0.2s ease-in-out',
        '&:hover': {
          boxShadow: 2
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
          {territory.isBuiltIn && (
            <Chip 
              label="Built-in" 
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
            {loading ? '...' : accountsCount}
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
      <CardActions sx={{ justifyContent: 'space-between', px: 2, py: 1.5 }}>
        {/* Explore button */}
        <Button
          variant="contained"
          size="small"
          endIcon={<ArrowRightOutlined />}
          onClick={isAccountType ? handleExploreAccounts : handleExploreContacts}
          disabled={isContactType}
        >
          {isContactType ? 'Coming soon' : 'Explore Accounts'}
        </Button>

        {/* Action icons */}
        <Stack direction="row" spacing={0}>
          <Tooltip title="Edit">
            <span>
              <IconButton 
                size="small" 
                onClick={handleEdit}
                disabled={territory.isBuiltIn}
              >
                <EditOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Duplicate">
            <IconButton size="small" onClick={handleDuplicate} disabled>
              <CopyOutlined style={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <span>
              <IconButton 
                size="small" 
                onClick={handleDelete}
                disabled={territory.isBuiltIn}
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
    type: PropTypes.oneOf(['account', 'contact']).isRequired,
    description: PropTypes.string,
    isBuiltIn: PropTypes.bool,
    filters: PropTypes.object
  }).isRequired,
  accountsCount: PropTypes.number,
  loading: PropTypes.bool
};