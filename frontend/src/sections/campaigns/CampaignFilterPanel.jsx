// frontend/src/sections/campaigns/CampaignFilterPanel.jsx

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

// project imports
import AsyncUserSelect from "components/AsyncSelection/AsyncUserSelect";
import AsyncTeamSelect from "components/AsyncSelection/AsyncTeamSelect";

// api
import { useGetTerritories } from "api/territories/territories";

// icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import DownOutlined from "@ant-design/icons/DownOutlined";
import FilterOutlined from "@ant-design/icons/FilterOutlined";
import ClearOutlined from "@ant-design/icons/ClearOutlined";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "DRAFT", label: "Draft" },
  { value: "ACTIVE", label: "Active" },
  { value: "PAUSED", label: "Paused" },
  { value: "COMPLETED", label: "Completed" },
  { value: "CANCELLED", label: "Cancelled" },
];

const TYPE_OPTIONS = [
  { value: "", label: "All types" },
  { value: "OUTBOUND", label: "Outbound" },
  { value: "TARGETED", label: "Targeted" },
];

const CHANNEL_OPTIONS = [
  { value: "", label: "All channels" },
  { value: "AUTO", label: "Auto" },
  { value: "NO_CALLS", label: "No calls" },
];

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

// ==============================|| CAMPAIGN FILTER PANEL ||============================== //

export default function CampaignFilterPanel({
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
  const { territories = [] } = useGetTerritories({ page: 1, pageSize: 100 });

  const set = (key) => (e) => onFilterChange(key, e.target.value);

  const handleApply = () => {
    onApply?.();
    onClose?.();
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: "100%", sm: 400 } } }}
    >
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

      <Box sx={{ flexGrow: 1, overflow: "auto" }}>
        <FilterSection
          title="Campaign"
          icon={<FilterOutlined style={{ fontSize: 16, color: "#8c8c8c" }} />}
          defaultExpanded={true}
        >
          <Stack spacing={2.5}>
            <FormControl fullWidth size="small">
              <InputLabel id="camp-status-label">Status</InputLabel>
              <Select
                labelId="camp-status-label"
                label="Status"
                value={pendingFilters?.status || ""}
                onChange={set("status")}
              >
                {STATUS_OPTIONS.map((o) => (
                  <MenuItem key={o.value || "all"} value={o.value}>
                    {o.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth size="small">
              <InputLabel id="camp-type-label">Type</InputLabel>
              <Select
                labelId="camp-type-label"
                label="Type"
                value={pendingFilters?.campaign_type || ""}
                onChange={set("campaign_type")}
              >
                {TYPE_OPTIONS.map((o) => (
                  <MenuItem key={o.value || "all"} value={o.value}>
                    {o.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth size="small">
              <InputLabel id="camp-territory-label">Territory</InputLabel>
              <Select
                labelId="camp-territory-label"
                label="Territory"
                value={pendingFilters?.territories || ""}
                onChange={set("territories")}
              >
                <MenuItem value="">All territories</MenuItem>
                {territories.map((t) => (
                  <MenuItem key={t.id} value={t.id}>
                    {t.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <AsyncUserSelect
              value={pendingFilters?.executor || null}
              onChange={(event, user) =>
                onFilterChange("executor", user || null)
              }
              label="Executor"
              placeholder="All executors"
              size="small"
            />

            <FormControl fullWidth size="small">
              <InputLabel id="camp-channel-label">Channel strategy</InputLabel>
              <Select
                labelId="camp-channel-label"
                label="Channel strategy"
                value={pendingFilters?.channel_override || ""}
                onChange={set("channel_override")}
              >
                {CHANNEL_OPTIONS.map((o) => (
                  <MenuItem key={o.value || "all"} value={o.value}>
                    {o.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <AsyncTeamSelect
              value={pendingFilters?.team || null}
              onChange={(event, team) => onFilterChange("team", team || null)}
              label="Team"
              placeholder="All teams"
              size="small"
            />

            <AsyncUserSelect
              value={pendingFilters?.owner || null}
              onChange={(event, user) => onFilterChange("owner", user || null)}
              label="Owner"
              placeholder="All owners"
              size="small"
            />

            <Box>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mb: 1, display: "block" }}
              >
                Owner scope
              </Typography>
              <FormControl component="fieldset" fullWidth>
                <RadioGroup
                  value={pendingFilters?.owner_scope || "all"}
                  onChange={set("owner_scope")}
                  sx={{ gap: 0.5 }}
                >
                  <FormControlLabel
                    value="mine"
                    control={<Radio size="small" />}
                    label="Mine"
                    sx={{ "& .MuiFormControlLabel-label": { fontSize: "0.875rem" } }}
                  />
                  <FormControlLabel
                    value="team"
                    control={<Radio size="small" />}
                    label="My Team"
                    sx={{ "& .MuiFormControlLabel-label": { fontSize: "0.875rem" } }}
                  />
                  <FormControlLabel
                    value="all"
                    control={<Radio size="small" />}
                    label="All"
                    sx={{ "& .MuiFormControlLabel-label": { fontSize: "0.875rem" } }}
                  />
                </RadioGroup>
              </FormControl>
            </Box>
          </Stack>
        </FilterSection>
      </Box>

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
            {loading ? "..." : `${matchingCount} campaigns`}
          </Typography>
        </Stack>
        <Stack direction="row" spacing={1}>
          <Button
            fullWidth
            variant="outlined"
            color="secondary"
            startIcon={<ClearOutlined />}
            onClick={onClear}
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

CampaignFilterPanel.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  pendingFilters: PropTypes.object,
  onFilterChange: PropTypes.func.isRequired,
  onApply: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
  hasPendingChanges: PropTypes.bool,
  matchingCount: PropTypes.number,
  loading: PropTypes.bool,
};
