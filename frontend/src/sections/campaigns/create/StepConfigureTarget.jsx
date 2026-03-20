// frontend/src/sections/campaigns/create/StepConfigureTarget.jsx
/**
 * Campaign Create Wizard — Step 1: Configure Target
 *
 * OUTBOUND only — Territory multi-selector + preview.
 * TARGETED campaign creation removed (singleton, managed separately).
 */

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

// material-ui
import { alpha, useTheme } from "@mui/material/styles";
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
import { useGetTerritories } from "api/territories/territories";

// icons
import AimOutlined from "@ant-design/icons/AimOutlined";
import GlobalOutlined from "@ant-design/icons/GlobalOutlined";

// ==============================|| STEP CONFIGURE TARGET ||============================== //

export default function StepConfigureTarget({
  territoryIds,
  selectedTerritories,
  onUpdate,
}) {
  const theme = useTheme();

  const { territories = [], territoriesLoading } = useGetTerritories({
    page: 1,
    pageSize: 100,
  });

  const resolvedTerritories = useMemo(() => {
    if (!territoryIds?.length) return [];
    return territories.filter((t) => territoryIds.includes(t.id));
  }, [territories, territoryIds]);

  const handleTerritoryChange = (event) => {
    const ids = event.target.value;
    const selected = territories.filter((t) => ids.includes(t.id));
    onUpdate({
      territory_ids: ids,
      selectedTerritories: selected,
    });
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 1 }}>
        Select territories
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        The territories define which accounts will be targeted in this campaign.
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
                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
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
                {resolvedTerritories.length > 1 ? "ies" : "y"} will be targeted
                when the campaign starts.
              </Typography>
            </Box>
          </Stack>
        </Box>
      )}
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

StepConfigureTarget.propTypes = {
  territoryIds: PropTypes.array,
  selectedTerritories: PropTypes.array,
  onUpdate: PropTypes.func.isRequired,
};
