// frontend/src/sections/businessData/decisionCycles/DecisionCycleFilterPanel.jsx

import PropTypes from "prop-types";

// material-ui
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Drawer from "@mui/material/Drawer";
import FormControl from "@mui/material/FormControl";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import DownOutlined from "@ant-design/icons/DownOutlined";
import FilterOutlined from "@ant-design/icons/FilterOutlined";
import ClearOutlined from "@ant-design/icons/ClearOutlined";

// project imports
import AsyncAccountSelect from "components/AsyncSelection/AsyncAccountSelect";

// ==============================|| STATUS OPTIONS ||============================== //

/**
 * Status options. "Open" maps to outcome__isnull=true; each terminal value maps
 * to outcome=<value> (exact). Both params are honoured by the backend
 * DecisionCycleViewSet filterset (outcome: ['exact', 'isnull']).
 */
const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "OPEN", label: "Open" },
  { value: "WON", label: "Won" },
  { value: "LOST", label: "Lost" },
  { value: "ON_HOLD", label: "On Hold" },
  { value: "NOT_QUALIFIED", label: "Not Qualified" },
];

// ==============================|| FILTER SECTION ||============================== //

function FilterSection({ title, icon, defaultExpanded = true, children }) {
  return (
    <Accordion defaultExpanded={defaultExpanded} disableGutters elevation={0}>
      <AccordionSummary
        expandIcon={<DownOutlined />}
        sx={{
          bgcolor: "grey.50",
          "&:hover": { bgcolor: "grey.100" },
          minHeight: 48,
          "& .MuiAccordionSummary-content": { my: 1 },
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          {icon}
          <Typography variant="subtitle2">{title}</Typography>
        </Stack>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 2, pb: 3 }}>{children}</AccordionDetails>
    </Accordion>
  );
}

FilterSection.propTypes = {
  title: PropTypes.string.isRequired,
  icon: PropTypes.node,
  defaultExpanded: PropTypes.bool,
  children: PropTypes.node,
};

// ==============================|| DECISION CYCLE FILTER PANEL ||============================== //

/**
 * Slide-in drawer for decision-cycle filters. Same shape as the account
 * TerritoryFilterPanel: header, filter section, footer with matching count +
 * Clear/Apply. Facets: Account, Status, and Owner scope (Mine / My Team / All).
 */
export default function DecisionCycleFilterPanel({
  open,
  onClose,
  pendingFilters,
  onFilterChange,
  onApply,
  onClear,
  hasPendingChanges,
  matchingCount = 0,
  loading = false,
}) {
  // ==============================|| HANDLERS ||============================== //

  const handleAccountChange = (account) => {
    onFilterChange("account", account || null);
  };

  const handleStatusChange = (event) => {
    onFilterChange("status", event.target.value);
  };

  const handleOwnerScopeChange = (event) => {
    onFilterChange("owner_scope", event.target.value);
  };

  const handleApply = () => {
    onApply?.();
    onClose?.();
  };

  const handleClear = () => {
    onClear?.();
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: "100%", sm: 400 } } }}
    >
      {/* ==================== HEADER ==================== */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ p: 2, borderBottom: 1, borderColor: "divider" }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <FilterOutlined style={{ fontSize: 20 }} />
          <Typography variant="h5">Filters</Typography>
        </Stack>
        <IconButton onClick={onClose} size="small">
          <CloseOutlined />
        </IconButton>
      </Stack>

      {/* ==================== FILTER SECTIONS ==================== */}
      <Box sx={{ flexGrow: 1, overflow: "auto" }}>
        <FilterSection
          title="Decision Cycle"
          icon={<FilterOutlined style={{ fontSize: 16, color: "#8c8c8c" }} />}
          defaultExpanded={true}
        >
          <Stack spacing={2.5}>
            {/* Account filter */}
            <AsyncAccountSelect
              value={pendingFilters?.account || null}
              onChange={handleAccountChange}
              label="Account"
              placeholder="All accounts"
              size="small"
            />

            {/* Status filter */}
            <FormControl fullWidth size="small">
              <InputLabel id="dc-status-filter-label">Status</InputLabel>
              <Select
                labelId="dc-status-filter-label"
                label="Status"
                value={pendingFilters?.status || ""}
                onChange={handleStatusChange}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value || "all"} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Owner scope filter */}
            <Box>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mb: 1, display: "block" }}
              >
                Owner
              </Typography>
              <FormControl component="fieldset" fullWidth>
                <RadioGroup
                  value={pendingFilters?.owner_scope || "all"}
                  onChange={handleOwnerScopeChange}
                  sx={{ gap: 0.5 }}
                >
                  <FormControlLabel
                    value="mine"
                    control={<Radio size="small" />}
                    label="Mine"
                    sx={{
                      "& .MuiFormControlLabel-label": { fontSize: "0.875rem" },
                    }}
                  />
                  <FormControlLabel
                    value="team"
                    control={<Radio size="small" />}
                    label="My Team"
                    sx={{
                      "& .MuiFormControlLabel-label": { fontSize: "0.875rem" },
                    }}
                  />
                  <FormControlLabel
                    value="all"
                    control={<Radio size="small" />}
                    label="All"
                    sx={{
                      "& .MuiFormControlLabel-label": { fontSize: "0.875rem" },
                    }}
                  />
                </RadioGroup>
              </FormControl>
            </Box>
          </Stack>
        </FilterSection>
      </Box>

      {/* ==================== FOOTER ==================== */}
      <Box sx={{ borderTop: 1, borderColor: "divider", p: 2 }}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          sx={{ mb: 2 }}
        >
          <Typography variant="body2" color="text.secondary">
            Matching:
          </Typography>
          <Typography variant="subtitle1" fontWeight={600}>
            {loading ? "..." : `${matchingCount} decision cycles`}
          </Typography>
        </Stack>

        <Stack direction="row" spacing={1}>
          <Button
            fullWidth
            variant="outlined"
            color="secondary"
            startIcon={<ClearOutlined />}
            onClick={handleClear}
          >
            Clear all
          </Button>
          <Button
            fullWidth
            variant="contained"
            onClick={handleApply}
            disabled={!hasPendingChanges}
          >
            Apply
          </Button>
        </Stack>
      </Box>
    </Drawer>
  );
}

// ==============================|| PROP TYPES ||============================== //

DecisionCycleFilterPanel.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  pendingFilters: PropTypes.shape({
    owner_scope: PropTypes.string,
    account: PropTypes.oneOfType([PropTypes.object, PropTypes.string]),
    status: PropTypes.string,
  }),
  onFilterChange: PropTypes.func.isRequired,
  onApply: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
  hasPendingChanges: PropTypes.bool,
  matchingCount: PropTypes.number,
  loading: PropTypes.bool,
};
