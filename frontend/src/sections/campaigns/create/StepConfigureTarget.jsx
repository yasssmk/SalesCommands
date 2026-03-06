// frontend/src/sections/campaigns/create/StepConfigureTarget.jsx
/**
 * Campaign Create Wizard
 *
 * Outbound  → Territory dropdown (useGetTerritories) + preview "X accounts"
 * Targeted  → Account multi-selector (AsyncAccountSelect multiple) + preview "X contacts"
 */

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

// material-ui
import { alpha, useTheme } from "@mui/material/styles";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Checkbox from "@mui/material/Checkbox";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import AsyncAccountSelect from "components/AsyncSelection/AsyncAccountSelect";
import { SEQUENCE_TYPES } from "api/campaigns/campaigns";
import { useGetTerritories } from "api/territories/territories";

// icons
import AimOutlined from "@ant-design/icons/AimOutlined";
import ThunderboltOutlined from "@ant-design/icons/ThunderboltOutlined";
import BankOutlined from "@ant-design/icons/BankOutlined";
import GlobalOutlined from "@ant-design/icons/GlobalOutlined";

// ==============================|| STEP CONFIGURE TARGET ||============================== //

export default function StepConfigureTarget({
  family,
  territoryIds,
  selectedTerritories,
  accountIds,
  selectedAccounts,
  onUpdate,
}) {
  const theme = useTheme();
  const isOutbound = family === SEQUENCE_TYPES.OUTBOUND;

  // ==============================|| PROSPECTION: TERRITORIES ||============================== //

  const { territories = [], territoriesLoading } = useGetTerritories({
    page: 1,
    pageSize: 100,
  });

  // Find selected territories for preview
  const resolvedTerritories = useMemo(() => {
    if (!territoryIds?.length) return [];
    return territories.filter((t) => territoryIds.includes(t.id));
  }, [territories, territoryIds]);

  // ==============================|| HANDLERS ||============================== //

  const handleTerritoryChange = (event) => {
    const ids = event.target.value; // MUI Select multiple returns array
    const selected = territories.filter((t) => ids.includes(t.id));
    onUpdate({
      territory_ids: ids,
      selectedTerritories: selected,
    });
  };

  const handleAccountsChange = (event, newValue) => {
    // newValue is an array of account objects (multiple mode)
    const accounts = Array.isArray(newValue) ? newValue : [];
    onUpdate({
      account_ids: accounts.map((a) => a.id),
      selectedAccounts: accounts,
    });
  };

  const handleRemoveAccount = (accountId) => {
    const updated = (selectedAccounts || []).filter((a) => a.id !== accountId);
    onUpdate({
      account_ids: updated.map((a) => a.id),
      selectedAccounts: updated,
    });
  };

  // ==============================|| RENDER: PROSPECTION ||============================== //

  if (isOutbound) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 1 }}>
          Select territories
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          The territories define which accounts will be targeted in this
          campaign.
        </Typography>

        {/* Territory Dropdown */}
        <Stack spacing={1} sx={{ mb: 3 }}>
          <InputLabel htmlFor="territory-select">Territories *</InputLabel>
          <FormControl fullWidth>
            <Select
              id="territory-select"
              multiple
              value={territoryIds || []}
              onChange={handleTerritoryChange}
              displayEmpty
              disabled={territoriesLoading}
              renderValue={(selected) => {
                if (!selected || selected.length === 0) {
                  return (
                    <Typography color="text.secondary">
                      {territoriesLoading
                        ? "Loading territories..."
                        : "Select territories"}
                    </Typography>
                  );
                }
                return (
                  <Stack
                    direction="row"
                    spacing={0.5}
                    flexWrap="wrap"
                    useFlexGap
                  >
                    {selected.map((id) => {
                      const t = territories.find((t) => t.id === id);
                      return (
                        <Chip
                          key={id}
                          icon={<GlobalOutlined style={{ fontSize: 14 }} />}
                          label={t?.name || id}
                          size="small"
                          variant="outlined"
                        />
                      );
                    })}
                  </Stack>
                );
              }}
            >
              {territories.map((territory) => (
                <MenuItem key={territory.id} value={territory.id}>
                  <Checkbox
                    checked={(territoryIds || []).includes(territory.id)}
                  />
                  <Stack direction="row" spacing={1.5} alignItems="center">
                    <GlobalOutlined
                      style={{
                        fontSize: 16,
                        color: theme.palette.text.secondary,
                      }}
                    />
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
        {resolvedTerritories.length > 0 && (
          <Box
            sx={{
              p: 2,
              borderRadius: 1.5,
              bgcolor: alpha(theme.palette.primary.main, 0.06),
              border: "1px solid",
              borderColor: alpha(theme.palette.primary.main, 0.15),
            }}
          >
            <Stack direction="row" spacing={1.5} alignItems="center">
              <AimOutlined
                style={{ fontSize: 20, color: theme.palette.primary.main }}
              />
              <Box>
                <Typography variant="subtitle2">
                  {resolvedTerritories.map((t) => t.name).join(", ")}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Accounts from {resolvedTerritories.length} territor
                  {resolvedTerritories.length > 1 ? "ies" : "y"} will be
                  targeted when the campaign starts.
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
        Choose one or more accounts. Their contacts will be added to the chasing
        campaign.
      </Typography>

      {/* Account Multi-Selector */}
      <Stack spacing={1} sx={{ mb: 3 }}>
        <InputLabel>Accounts *</InputLabel>
        <AsyncAccountSelect
          value={null}
          onChange={(event, newValue) => {
            // AsyncSelect onChange gives (event, newValue)
            // Add to selection if not already present
            if (
              newValue &&
              !(selectedAccounts || []).find((a) => a.id === newValue.id)
            ) {
              const updated = [...(selectedAccounts || []), newValue];
              onUpdate({
                account_ids: updated.map((a) => a.id),
                selectedAccounts: updated,
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
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{
              textTransform: "uppercase",
              fontSize: "0.75rem",
              fontWeight: 600,
              letterSpacing: "0.5px",
            }}
          >
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
              border: "1px solid",
              borderColor: alpha(theme.palette.warning.main, 0.15),
            }}
          >
            <Stack direction="row" spacing={1.5} alignItems="center">
              <ThunderboltOutlined
                style={{ fontSize: 20, color: theme.palette.warning.main }}
              />
              <Typography variant="body2" color="text.secondary">
                Contacts from <strong>{selectedAccounts.length}</strong> account
                {selectedAccounts.length > 1 ? "s" : ""} will be added to the
                targeted campaign.
              </Typography>
            </Stack>
          </Box>
        </Stack>
      )}

      {/* Existing campaign hint (MVP placeholder) */}
      {(selectedAccounts || []).length > 0 && (
        <Alert severity="info" sx={{ mt: 2 }}>
          If an active targeted campaign already exists, contacts will be added
          to it instead of creating a new one.
        </Alert>
      )}
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

StepConfigureTarget.propTypes = {
  /** Campaign family: OUTBOUND or TARGETED */
  family: PropTypes.string.isRequired,
  /** Selected territory IDs (Outbound) */
  territoryIds: PropTypes.array,
  /** Selected territory objects (Outbound) — kept for display */
  selectedTerritories: PropTypes.array,
  /** Selected account IDs (Targeted) */
  accountIds: PropTypes.array,
  /** Selected account objects (Targeted) — kept for chips display */
  selectedAccounts: PropTypes.array,
  /** Callback to update wizard data: (updates) => void */
  onUpdate: PropTypes.func.isRequired,
};
