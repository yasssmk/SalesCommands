// frontend/src/sections/campaigns/create/StepConfigureTarget.jsx
/**
 * Campaign Create Wizard — Step 1: Configure Target
 *
 * Prospection → Territory dropdown (useGetTerritories) + preview "X accounts"
 * Chasing    → Account multi-selector (AsyncAccountSelect multiple) + preview "X contacts"
 */

'use client';

import PropTypes from 'prop-types';
import { useMemo } from 'react';

// material-ui
import { alpha, useTheme } from '@mui/material/styles';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import AsyncAccountSelect from 'components/AsyncSelection/AsyncAccountSelect';
import { CAMPAIGN_FAMILIES } from 'api/campaigns/campaigns';
import { useGetTerritories } from 'api/territories/territories';

// icons
import AimOutlined from '@ant-design/icons/AimOutlined';
import ThunderboltOutlined from '@ant-design/icons/ThunderboltOutlined';
import BankOutlined from '@ant-design/icons/BankOutlined';
import GlobalOutlined from '@ant-design/icons/GlobalOutlined';

// ==============================|| STEP CONFIGURE TARGET ||============================== //

export default function StepConfigureTarget({
  family,
  territoryId,
  territoryName,
  accountIds,
  selectedAccounts,
  onUpdate
}) {
  const theme = useTheme();
  const isProspection = family === CAMPAIGN_FAMILIES.PROSPECTION;

  // ==============================|| PROSPECTION: TERRITORIES ||============================== //

  const {
    territories = [],
    territoriesLoading
  } = useGetTerritories({ page: 1, pageSize: 100 });

  // Find selected territory for preview
  const selectedTerritory = useMemo(() => {
    return territories.find((t) => t.id === territoryId) || null;
  }, [territories, territoryId]);

  // ==============================|| HANDLERS ||============================== //

  const handleTerritoryChange = (event) => {
    const id = event.target.value;
    const territory = territories.find((t) => t.id === id);
    onUpdate({
      territory_id: id,
      territory_name: territory?.name || ''
    });
  };

  const handleAccountsChange = (event, newValue) => {
    // newValue is an array of account objects (multiple mode)
    const accounts = Array.isArray(newValue) ? newValue : [];
    onUpdate({
      account_ids: accounts.map((a) => a.id),
      selectedAccounts: accounts
    });
  };

  const handleRemoveAccount = (accountId) => {
    const updated = (selectedAccounts || []).filter((a) => a.id !== accountId);
    onUpdate({
      account_ids: updated.map((a) => a.id),
      selectedAccounts: updated
    });
  };

  // ==============================|| RENDER: PROSPECTION ||============================== //

  if (isProspection) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 1 }}>
          Select a territory
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          The territory defines which accounts will be targeted in this campaign.
        </Typography>

        {/* Territory Dropdown */}
        <Stack spacing={1} sx={{ mb: 3 }}>
          <InputLabel htmlFor="territory-select">Territory *</InputLabel>
          <FormControl fullWidth>
            <Select
              id="territory-select"
              value={territoryId || ''}
              onChange={handleTerritoryChange}
              displayEmpty
              disabled={territoriesLoading}
              renderValue={(value) => {
                if (!value) {
                  return (
                    <Typography color="text.secondary">
                      {territoriesLoading ? 'Loading territories...' : 'Select a territory'}
                    </Typography>
                  );
                }
                const t = territories.find((t) => t.id === value);
                return (
                  <Stack direction="row" spacing={1} alignItems="center">
                    <GlobalOutlined style={{ fontSize: 16, color: theme.palette.primary.main }} />
                    <Typography>{t?.name || value}</Typography>
                  </Stack>
                );
              }}
            >
              {territories.map((territory) => (
                <MenuItem key={territory.id} value={territory.id}>
                  <Stack direction="row" spacing={1.5} alignItems="center">
                    <GlobalOutlined style={{ fontSize: 16, color: theme.palette.text.secondary }} />
                    <Box>
                      <Typography variant="body1">{territory.name}</Typography>
                      {territory.description && (
                        <Typography variant="caption" color="text.secondary">
                          {territory.description}
                        </Typography>
                      )}
                    </Box>
                  </Stack>
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>

        {/* Preview */}
        {selectedTerritory && (
          <Box
            sx={{
              p: 2,
              borderRadius: 1.5,
              bgcolor: alpha(theme.palette.primary.main, 0.06),
              border: '1px solid',
              borderColor: alpha(theme.palette.primary.main, 0.15)
            }}
          >
            <Stack direction="row" spacing={1.5} alignItems="center">
              <AimOutlined style={{ fontSize: 20, color: theme.palette.primary.main }} />
              <Box>
                <Typography variant="subtitle2">
                  {selectedTerritory.name}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Accounts from this territory will be targeted when the campaign starts.
                </Typography>
              </Box>
            </Stack>
          </Box>
        )}
      </Box>
    );
  }

  // ==============================|| RENDER: CHASING ||============================== //

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 1 }}>
        Select accounts to chase
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Choose one or more accounts. Their contacts will be added to the chasing campaign.
      </Typography>

      {/* Account Multi-Selector */}
      <Stack spacing={1} sx={{ mb: 3 }}>
        <InputLabel>Accounts *</InputLabel>
        <AsyncAccountSelect
          value={null}
          onChange={(event, newValue) => {
            // AsyncSelect onChange gives (event, newValue)
            // Add to selection if not already present
            if (newValue && !(selectedAccounts || []).find((a) => a.id === newValue.id)) {
              const updated = [...(selectedAccounts || []), newValue];
              onUpdate({
                account_ids: updated.map((a) => a.id),
                selectedAccounts: updated
              });
            }
          }}
          label=""
          placeholder="Search accounts by name..."
          excludeIds={accountIds || []}
        />
      </Stack>

      {/* Selected Accounts Chips */}
      {(selectedAccounts || []).length > 0 && (
        <Stack spacing={2}>
          <Typography variant="subtitle2" color="text.secondary" sx={{ textTransform: 'uppercase', fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.5px' }}>
            Selected Accounts ({selectedAccounts.length})
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {selectedAccounts.map((account) => (
              <Chip
                key={account.id}
                icon={<BankOutlined style={{ fontSize: 14 }} />}
                label={account.company_name || account.id}
                onDelete={() => handleRemoveAccount(account.id)}
                variant="outlined"
                size="small"
                sx={{ mb: 0.5 }}
              />
            ))}
          </Stack>

          {/* Preview */}
          <Box
            sx={{
              p: 2,
              borderRadius: 1.5,
              bgcolor: alpha(theme.palette.warning.main, 0.06),
              border: '1px solid',
              borderColor: alpha(theme.palette.warning.main, 0.15)
            }}
          >
            <Stack direction="row" spacing={1.5} alignItems="center">
              <ThunderboltOutlined style={{ fontSize: 20, color: theme.palette.warning.main }} />
              <Typography variant="body2" color="text.secondary">
                Contacts from <strong>{selectedAccounts.length}</strong> account{selectedAccounts.length > 1 ? 's' : ''} will be added to the chasing campaign.
              </Typography>
            </Stack>
          </Box>
        </Stack>
      )}

      {/* Existing campaign hint (MVP placeholder) */}
      {(selectedAccounts || []).length > 0 && (
        <Alert severity="info" sx={{ mt: 2 }}>
          If an active chasing campaign already exists, contacts will be added to it instead of creating a new one.
        </Alert>
      )}
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

StepConfigureTarget.propTypes = {
  /** Campaign family: PROSPECTION or CHASING */
  family: PropTypes.string.isRequired,
  /** Selected territory ID (Prospection) */
  territoryId: PropTypes.string,
  /** Selected territory name (Prospection) */
  territoryName: PropTypes.string,
  /** Selected account IDs (Chasing) */
  accountIds: PropTypes.array,
  /** Selected account objects (Chasing) — kept for chips display */
  selectedAccounts: PropTypes.array,
  /** Callback to update wizard data: (updates) => void */
  onUpdate: PropTypes.func.isRequired
};