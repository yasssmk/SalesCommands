// frontend/src/components/cards/signals/TechStackCard.jsx
/**
 * TechStackCard — display card for a single TechStackSignal.
 *
 * Used by SignalList when signalType === 'tech-stack', in place of the
 * generic SignalCard (which is kept for People only — Pain and
 * Objective also have dedicated cards).
 *
 * Responsibilities:
 *   - Render TechStack header (type chip, status chip, canonical chip
 *     "{vendor} {product}", strategic badges, creation date)
 *   - Render body: usage scope + department (when applicable),
 *     lifecycle compact line, discontinuation badge, notes truncated
 *   - Surface lifecycle actions (validate, reject, edit, delete) aligned
 *     with PainCard / ObjectiveCard conventions
 *   - Confirm destructive delete via inline dialog
 *
 * Contract — the parent (AccountSignalsTab / ActivitySignalsTab) owns:
 *   - SignalEditDialog opening for TechStack edit
 *   - API calls for validate / reject / delete
 *
 * TechStackCard only emits callbacks; it never calls the API directly.
 *
 * Design notes:
 *   - Uses `primary` color palette as the TechStack visual identity,
 *     distinct from Pain's `error`, Objective's `info`, People's `secondary`.
 *   - Border emphasis is competitor/integration-aware: a competitor tool
 *     is a strong commercial signal and earns a prominent error border;
 *     an integration target earns an info border. Pending status takes
 *     precedence over both (warning border) — the rep's first action
 *     is always to validate.
 *   - Lifecycle line collapses null fields silently — a tool with only
 *     a renewal date should read "Renewal Sep 2025", not "— · Renewal
 *     Sep 2025 · —".
 *   - No nested sub-resource (unlike PainCard/PainImpact). The
 *     "all_observations" drill-down lives in SignalClusterDetailDrawer
 *     (cluster surface), not at the individual signal level.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// ant-design icons
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";
import MoreOutlined from "@ant-design/icons/MoreOutlined";
import StopOutlined from "@ant-design/icons/StopOutlined";

// ==============================|| STATUS CONFIG ||============================== //

const STATUS_CONFIG = {
  PENDING: { color: "warning", label: "Pending" },
  VALIDATED: { color: "success", label: "Validated" },
  REJECTED: { color: "error", label: "Rejected" },
};

// ==============================|| USAGE SCOPE CONFIG ||============================== //

/**
 * Visual tag per UsageScope — distinct from Pain's ScopeLevel palette.
 *
 * Rationale: ScopeLevel (BUSINESS / DEPARTMENT / PERSONAL) is about
 * the LEVEL of evidence; UsageScope (TEAM / DEPARTMENT / COMPANY /
 * UNKNOWN) is about the BREADTH of tool usage. Different concept,
 * different palette to avoid visual confusion when a card mixes both.
 *
 *   TEAM       → secondary (purple) — narrow, granular
 *   DEPARTMENT → info      (blue)   — clearly delimited
 *   COMPANY    → success   (green)  — broad reach, strong signal
 *   UNKNOWN    → default   (grey)   — neutral, missing data
 */
const USAGE_SCOPE_CONFIG = {
  TEAM: { color: "secondary", label: "Team" },
  DEPARTMENT: { color: "info", label: "Department" },
  COMPANY: { color: "success", label: "Company-wide" },
  UNKNOWN: { color: "default", label: "Unknown scope" },
};

// ==============================|| HELPERS ||============================== //

function formatShortDate(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return null;
  }
}

function truncate(str, max = 120) {
  if (!str) return null;
  return str.length > max ? `${str.slice(0, max)}…` : str;
}

/**
 * Build the canonical display label from a tech_catalog_entry payload.
 *
 * The backend serializer returns a compact dict
 * { id, company_name, product_name, is_competitor, is_integration_target }
 * — never null when the signal exists (catalog FK is required at create time).
 * Defensive fallback to "Unknown tool" guards against malformed reads.
 */
function getCatalogLabel(entry) {
  if (!entry) return "Unknown tool";
  const company = entry.company_name?.trim() || "";
  const product = entry.product_name?.trim() || "";
  if (!company && !product) return "Unknown tool";
  if (!company) return product;
  if (!product || product === company) return company;
  return `${company} ${product}`;
}

// ==============================|| CONFIRM DIALOG ||============================== //

/**
 * Minimal inline confirm dialog for destructive actions. Local copy
 * mirrors the pattern in PainCard / ObjectiveCard — kept inline to
 * avoid cross-file coupling while the component library stabilises.
 */
function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  onConfirm,
  onClose,
}) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary">
          {message}
        </Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} color="inherit" size="small">
          Cancel
        </Button>
        <Button
          onClick={onConfirm}
          color="error"
          variant="contained"
          size="small"
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

ConfirmDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  title: PropTypes.string.isRequired,
  message: PropTypes.string.isRequired,
  confirmLabel: PropTypes.string.isRequired,
  onConfirm: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
};

// ==============================|| TECH STACK CARD ||============================== //

/**
 * TechStackCard
 *
 * @param {Object}   techStack    - TechStackSignal read payload
 * @param {Object}   choices      - From useGetSignalChoices() (currently
 *                                   unused — UsageScope is hard-coded;
 *                                   kept for signature parity)
 * @param {Function} onValidate   - (signal, 'tech-stack') => void
 * @param {Function} onReject     - (signal, 'tech-stack') => void
 * @param {Function} onEdit       - (signal, 'tech-stack') => void — opens SignalEditDialog
 * @param {Function} onDelete     - (signal, 'tech-stack') => void — parent handles API
 */
export default function TechStackCard({
  techStack,
  // eslint-disable-next-line no-unused-vars
  choices,
  onValidate,
  onReject,
  onEdit,
  onDelete,
}) {
  // ==============================|| LOCAL STATE ||============================== //

  const [menuAnchor, setMenuAnchor] = useState(null);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  // ==============================|| DERIVED ||============================== //

  const status = techStack.status ?? "PENDING";
  const statusCfg = STATUS_CONFIG[status] ?? {
    color: "default",
    label: status,
  };

  const isPending = status === "PENDING";

  const createdDate = formatShortDate(techStack.created_at);

  /** Catalog label — "Salesforce Sales Cloud" */
  const catalogLabel = useMemo(
    () => getCatalogLabel(techStack.tech_catalog_entry),
    [techStack.tech_catalog_entry],
  );

  /** Strategic flags from the catalog entry */
  const isCompetitor = Boolean(techStack.tech_catalog_entry?.is_competitor);
  const isIntegrationTarget = Boolean(
    techStack.tech_catalog_entry?.is_integration_target,
  );

  /** Usage scope chip config */
  const scopeCfg = useMemo(() => {
    if (!techStack.usage_scope) return null;
    return USAGE_SCOPE_CONFIG[techStack.usage_scope] ?? null;
  }, [techStack.usage_scope]);

  /** Department display name (when scope=DEPARTMENT) */
  const departmentName = useMemo(() => {
    const dept = techStack.usage_department;
    if (!dept) return null;
    if (typeof dept === "string") return dept;
    return dept.name ?? null;
  }, [techStack.usage_department]);

  /**
   * Lifecycle compact line — "Used since 2019 · Renewal Sep 2025 · ~80k€/year"
   * Each segment is included only when its source field is set, so a
   * tool with just a renewal date reads cleanly as "Renewal Sep 2025".
   */
  const lifecycleLine = useMemo(() => {
    const parts = [];

    if (techStack.usage_start_year) {
      parts.push(`Used since ${techStack.usage_start_year}`);
    }

    if (techStack.renewal_date) {
      const renewalLabel = formatShortDate(techStack.renewal_date);
      if (renewalLabel) parts.push(`Renewal ${renewalLabel}`);
    }

    if (techStack.cost_description?.trim()) {
      // Cost is free-text and may be long — truncate aggressively for
      // the inline line; full text is on the detail drawer.
      parts.push(truncate(techStack.cost_description.trim(), 50));
    }

    return parts.length > 0 ? parts.join(" · ") : null;
  }, [
    techStack.usage_start_year,
    techStack.renewal_date,
    techStack.cost_description,
  ]);

  /** Discontinuation display */
  const discontinuationLine = useMemo(() => {
    if (!techStack.is_discontinued) return null;
    const dateLabel = formatShortDate(techStack.discontinued_date);
    return dateLabel ? `Discontinued ${dateLabel}` : "Discontinued";
  }, [techStack.is_discontinued, techStack.discontinued_date]);

  /** Source line — "From Activity #abc12345" */
  const sourceLine = useMemo(() => {
    const activity = techStack.source_activity;
    if (!activity) return null;

    if (typeof activity === "string") {
      return `From Activity #${activity.slice(0, 8)}`;
    }

    const id = activity.id;
    const subject = activity.subject || activity.title;
    const rawDate =
      activity.completed_at || activity.scheduled_date || activity.due_date;

    let dateStr = "";
    if (rawDate) {
      try {
        dateStr = new Date(rawDate).toISOString().slice(0, 10);
      } catch {
        dateStr = String(rawDate).slice(0, 10);
      }
    }

    if (subject && dateStr) return `From ${subject} · ${dateStr}`;
    if (subject) return `From ${subject}`;
    if (dateStr) return `From ${dateStr}`;
    if (id) return `From Activity #${String(id).slice(0, 8)}`;
    return null;
  }, [techStack.source_activity]);

  /**
   * Border emphasis — composes status, discontinuation, and strategic
   * flags. Order of precedence:
   *   1. PENDING        → warning.light (universal — needs validation)
   *   2. is_competitor  → error.main (strong commercial signal)
   *   3. is_integration → info.main
   *   4. is_discontinued → divider (visual de-emphasis)
   *   5. default        → divider
   */
  const borderColor = useMemo(() => {
    if (isPending) return "warning.light";
    if (isCompetitor) return "error.main";
    if (isIntegrationTarget) return "info.main";
    return "divider";
  }, [isPending, isCompetitor, isIntegrationTarget]);

  /** Border thickness — competitors/integration get a stronger emphasis */
  const borderWidth = useMemo(() => {
    if (isCompetitor || isIntegrationTarget) return "2px";
    return "1px";
  }, [isCompetitor, isIntegrationTarget]);

  // ==============================|| MENU HANDLERS ||============================== //

  const handleMenuOpen = useCallback((e) => {
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
  }, []);

  const handleMenuClose = useCallback(() => setMenuAnchor(null), []);

  const handleEdit = useCallback(() => {
    handleMenuClose();
    onEdit(techStack, "tech-stack");
  }, [handleMenuClose, onEdit, techStack]);

  const handleDeleteRequest = useCallback(() => {
    handleMenuClose();
    setConfirmDeleteOpen(true);
  }, [handleMenuClose]);

  const handleDeleteConfirm = useCallback(() => {
    setConfirmDeleteOpen(false);
    onDelete(techStack, "tech-stack");
  }, [onDelete, techStack]);

  const handleValidate = useCallback(() => {
    onValidate(techStack, "tech-stack");
  }, [onValidate, techStack]);

  const handleReject = useCallback(() => {
    onReject(techStack, "tech-stack");
  }, [onReject, techStack]);

  // ==============================|| RENDER ||============================== //

  return (
    <Box
      sx={{
        border: `${borderWidth} solid`,
        borderColor,
        borderRadius: 1.5,
        p: 2,
        bgcolor: "background.paper",
        opacity: techStack.is_discontinued && !isPending ? 0.85 : 1,
        transition: "border-color 0.15s, opacity 0.15s",
        "&:hover": { borderColor: "primary.light" },
      }}
    >
      {/* ==================== HEADER ==================== */}
      <Stack direction="row" spacing={1} alignItems="flex-start">
        {/* Left: type chip + status chip + canonical + strategic badges + date */}
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ flex: 1, minWidth: 0 }}
        >
          <Chip
            label="Tech Stack"
            color="primary"
            size="small"
            variant="outlined"
            sx={{ fontSize: "0.68rem", height: 20 }}
          />
          <Chip
            label={statusCfg.label}
            color={statusCfg.color}
            size="small"
            sx={{ fontSize: "0.68rem", height: 20 }}
          />

          {/* Canonical chip — vendor + product, primary palette */}
          <Chip
            label={catalogLabel}
            size="small"
            color="primary"
            variant="outlined"
            sx={{ fontSize: "0.68rem", height: 20, fontWeight: 500 }}
          />

          {/* Strategic flags — competitor / integration target.
              These earn their own chip (not just the border) because
              the rep needs to spot them mid-list, not only when
              focusing on the card. */}
          {isCompetitor && (
            <Tooltip title="This vendor competes with us">
              <Chip
                label="Competitor"
                color="error"
                size="small"
                sx={{ fontSize: "0.62rem", height: 18 }}
              />
            </Tooltip>
          )}
          {isIntegrationTarget && (
            <Tooltip title="This vendor is an integration target">
              <Chip
                label="Integration"
                color="info"
                size="small"
                variant="outlined"
                sx={{ fontSize: "0.62rem", height: 18 }}
              />
            </Tooltip>
          )}

          {createdDate && (
            <Typography variant="caption" color="text.disabled">
              {createdDate}
            </Typography>
          )}
        </Stack>

        {/* Right: quick actions + overflow menu */}
        <Stack direction="row" spacing={0.5} alignItems="center" flexShrink={0}>
          {isPending && (
            <Tooltip title="Validate signal">
              <IconButton
                size="small"
                color="success"
                onClick={handleValidate}
                aria-label="Validate signal"
              >
                <CheckCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          {isPending && (
            <Tooltip title="Reject signal">
              <IconButton
                size="small"
                color="error"
                onClick={handleReject}
                aria-label="Reject signal"
              >
                <CloseCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          <IconButton
            size="small"
            onClick={handleMenuOpen}
            aria-label="Tech stack actions"
            aria-controls={menuAnchor ? "techstack-action-menu" : undefined}
            aria-haspopup="true"
            aria-expanded={Boolean(menuAnchor)}
          >
            <MoreOutlined style={{ fontSize: 16 }} />
          </IconButton>

          <Menu
            id="techstack-action-menu"
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={handleMenuClose}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            transformOrigin={{ vertical: "top", horizontal: "right" }}
          >
            {status !== "REJECTED" && (
              <MenuItem onClick={handleEdit} dense>
                <Stack direction="row" spacing={1} alignItems="center">
                  <EditOutlined style={{ fontSize: 14 }} />
                  <span>Edit signal</span>
                </Stack>
              </MenuItem>
            )}
            <MenuItem
              onClick={handleDeleteRequest}
              dense
              sx={{ color: "error.main" }}
            >
              <Stack direction="row" spacing={1} alignItems="center">
                <DeleteOutlined style={{ fontSize: 14 }} />
                <span>Delete signal</span>
              </Stack>
            </MenuItem>
          </Menu>
        </Stack>
      </Stack>

      {/* ==================== USAGE SCOPE ROW ==================== */}
      {(scopeCfg || departmentName) && (
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ mt: 1.25 }}
        >
          {scopeCfg && (
            <Chip
              label={scopeCfg.label}
              size="small"
              color={scopeCfg.color}
              variant="outlined"
              sx={{ fontSize: "0.65rem", height: 20 }}
            />
          )}
          {departmentName && techStack.usage_scope === "DEPARTMENT" && (
            <Typography variant="caption" color="text.secondary">
              {departmentName}
            </Typography>
          )}
        </Stack>
      )}

      {/* ==================== LIFECYCLE LINE ==================== */}
      {lifecycleLine && (
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          sx={{ mt: 1 }}
        >
          <CalendarOutlined style={{ fontSize: 13, color: "#8c8c8c" }} />
          <Typography
            variant="caption"
            color="text.secondary"
            title={
              // Tooltip-on-hover surfaces full cost_description if it
              // got truncated in the inline label.
              techStack.cost_description?.trim() || undefined
            }
          >
            {lifecycleLine}
          </Typography>
        </Stack>
      )}

      {/* ==================== DISCONTINUATION BADGE ==================== */}
      {discontinuationLine && (
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          sx={{
            mt: 1,
            py: 0.5,
            px: 1,
            bgcolor: "error.lighter",
            borderRadius: 0.75,
            border: "1px dashed",
            borderColor: "error.light",
            width: "fit-content",
          }}
        >
          <StopOutlined style={{ fontSize: 12, color: "#cf1322" }} />
          <Typography variant="caption" color="error.dark" fontWeight={500}>
            {discontinuationLine}
          </Typography>
        </Stack>
      )}

      {/* ==================== NOTES ==================== */}
      {techStack.notes && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            mt: 1.25,
          }}
          title={techStack.notes}
        >
          {techStack.notes}
        </Typography>
      )}

      {/* ==================== SOURCE LINE ==================== */}
      {sourceLine && (
        <>
          <Divider sx={{ mt: 1.5, mb: 1 }} />
          <Typography variant="caption" color="text.disabled">
            {sourceLine}
          </Typography>
        </>
      )}

      {/* ==================== CONFIRM: Delete ==================== */}
      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Delete this tech stack signal?"
        message="This signal will be deleted permanently. The catalog entry remains available for other signals."
        confirmLabel="Delete signal"
        onConfirm={handleDeleteConfirm}
        onClose={() => setConfirmDeleteOpen(false)}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

TechStackCard.propTypes = {
  techStack: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string,

    // Catalog anchor — compact dict from List/Detail serializer
    tech_catalog_entry: PropTypes.shape({
      id: PropTypes.string,
      company_name: PropTypes.string,
      product_name: PropTypes.string,
      is_competitor: PropTypes.bool,
      is_integration_target: PropTypes.bool,
    }),

    // Scope axis
    usage_scope: PropTypes.oneOf(["TEAM", "DEPARTMENT", "COMPANY", "UNKNOWN"]),
    usage_department: PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.shape({ id: PropTypes.string, name: PropTypes.string }),
    ]),

    // Lifecycle
    usage_start_year: PropTypes.number,
    renewal_date: PropTypes.string,
    cost_description: PropTypes.string,
    is_discontinued: PropTypes.bool,
    discontinued_date: PropTypes.string,

    // Narrative
    notes: PropTypes.string,

    // Source
    source_activity: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),

    // Audit
    created_at: PropTypes.string,
  }).isRequired,
  choices: PropTypes.object,

  /** Lifecycle actions — signature matches PainCard / ObjectiveCard */
  onValidate: PropTypes.func.isRequired,
  onReject: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
};
