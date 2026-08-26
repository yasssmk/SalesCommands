// frontend/src/components/cards/signals/ImpactCard.jsx
/**
 * ImpactCard — display card for a single ImpactSignal.
 *
 * Used by SignalList when signalType === 'impact', in place of the
 * generic SignalCard.
 *
 * Responsibilities:
 *   - Render Impact header (type chip, status chip, canonical axes,
 *     scope chip, creation date, actions)
 *   - Render Impact body (summary, the shared ImpactDetailBlock for
 *     impact_type / metric_text / human_impact, source provenance line)
 *   - Surface lifecycle actions (validate, reject, edit, delete) aligned
 *     with PainCard / ObjectiveCard / TechStackCard conventions
 *   - Confirm destructive delete via inline dialog
 *
 * Contract — the parent (AccountSignalsTab / ActivitySignalsTab) owns:
 *   - SignalEditDialog opening for Impact edit
 *   - API calls for validate / reject / delete
 *
 * ImpactCard only emits callbacks; it never calls the API directly.
 *
 * Design notes:
 *   - Uses `secondary` color palette (purple) as the Impact visual
 *     identity, distinct from Pain's `error` (red), Objective's `info`
 *     (blue), and TechStack's `primary` (default blue).
 *   - No nested sub-resource (unlike PainCard which renders
 *     PainImpacts) — Impact is a leaf signal type.
 *   - No `target_*` fields — Impact does not propagate ownership
 *     (contrary to Objective). All evidence is captured directly via
 *     impact_type / human_impact / metric_text fields.
 *   - impact_type / metric_text / human_impact are rendered by the
 *     shared ImpactDetailBlock (one visual truth across drawer + card).
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
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";
import MoreOutlined from "@ant-design/icons/MoreOutlined";

// Shared per-type detail block — single rendering of impact-specific fields
import ImpactDetailBlock from "components/signals/detail/ImpactDetailBlock";

// ==============================|| STATUS CONFIG ||============================== //

const STATUS_CONFIG = {
  PENDING: { color: "warning", label: "Pending" },
  VALIDATED: { color: "success", label: "Validated" },
  REJECTED: { color: "error", label: "Rejected" },
};

// ==============================|| SCOPE LEVEL CONFIG ||============================== //

/**
 * Visual tag per ScopeLevel — mirrors ObjectiveCard's palette so the
 * scope concept reads the same way across all signal types that carry
 * a scope_level field.
 */
const SCOPE_LEVEL_CONFIG = {
  BUSINESS: { color: "warning", label: "Business" },
  DEPARTMENT: { color: "info", label: "Department" },
  PERSONAL: { color: "error", label: "Personal" },
};

// ==============================|| HELPERS ||============================== //

function formatContact(contact) {
  if (!contact) return null;
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  return name || null;
}

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

function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

// ==============================|| CONFIRM DIALOG ||============================== //

/**
 * Minimal inline confirm dialog for destructive actions.
 * Same shape as the one in PainCard / ObjectiveCard — kept local to
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

// ==============================|| IMPACT CARD ||============================== //

/**
 * ImpactCard
 *
 * @param {Object}   impact      - ImpactSignal read payload
 * @param {Object}   choices     - From useGetSignalChoices()
 *                                  Expected keys: signal_whats, signal_dimensions,
 *                                  impact_types, human_impacts
 * @param {Function} onValidate  - (impact, 'impact') => void
 * @param {Function} onReject    - (impact, 'impact') => void
 * @param {Function} onEdit      - (impact, 'impact') => void — opens SignalEditDialog
 * @param {Function} onDelete    - (impact, 'impact') => void — parent handles API
 */
export default function ImpactCard({
  impact,
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

  const status = impact.status ?? "PENDING";
  const statusCfg = STATUS_CONFIG[status] ?? {
    color: "default",
    label: status,
  };

  const isPending = status === "PENDING";

  const createdDate = formatShortDate(impact.created_at);

  /** Canonical axes chip text — "Operations × Time" */
  const canonicalText = useMemo(() => {
    const whatLabel = resolveLabel(choices?.signal_whats, impact.what);
    const dimensionLabel = resolveLabel(
      choices?.signal_dimensions,
      impact.dimension,
    );
    if (!whatLabel || !dimensionLabel) return null;
    return `${whatLabel} × ${dimensionLabel}`;
  }, [choices, impact.what, impact.dimension]);

  /** Scope chip config */
  const scopeCfg = useMemo(
    () => SCOPE_LEVEL_CONFIG[impact.scope_level] ?? null,
    [impact.scope_level],
  );

  /** Source line — "From [contact] · 2026-04-15" derived from source_activity */
  const sourceLine = useMemo(() => {
    const activity = impact.source_activity;
    if (!activity) return null;

    const contacts = activity.contacts ?? [];
    let contactLabel = "";
    if (contacts.length === 1) {
      contactLabel = formatContact(contacts[0]) ?? "";
    } else if (contacts.length > 1) {
      contactLabel = `${contacts.length} contacts`;
    }

    const rawDate = activity.scheduled_date || activity.completed_at;
    let dateStr = "";
    if (rawDate) {
      try {
        dateStr = new Date(rawDate).toISOString().slice(0, 10);
      } catch {
        dateStr = String(rawDate).slice(0, 10);
      }
    }

    if (contactLabel && dateStr) {
      return `From ${contactLabel} · ${dateStr}`;
    }
    if (contactLabel) return `From ${contactLabel}`;
    if (dateStr) return dateStr;
    return null;
  }, [impact.source_activity]);

  // ==============================|| MENU HANDLERS ||============================== //

  const handleMenuOpen = useCallback((e) => {
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
  }, []);

  const handleMenuClose = useCallback(() => setMenuAnchor(null), []);

  const handleEdit = useCallback(() => {
    handleMenuClose();
    onEdit(impact, "impact");
  }, [handleMenuClose, onEdit, impact]);

  const handleDeleteRequest = useCallback(() => {
    handleMenuClose();
    setConfirmDeleteOpen(true);
  }, [handleMenuClose]);

  const handleDeleteConfirm = useCallback(() => {
    setConfirmDeleteOpen(false);
    onDelete(impact, "impact");
  }, [onDelete, impact]);

  const handleValidate = useCallback(() => {
    onValidate(impact, "impact");
  }, [onValidate, impact]);

  const handleReject = useCallback(() => {
    onReject(impact, "impact");
  }, [onReject, impact]);

  // ==============================|| RENDER ||============================== //

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: isPending ? "warning.light" : "divider",
        borderRadius: 1.5,
        p: 2,
        bgcolor: "background.paper",
        transition: "border-color 0.15s",
        "&:hover": { borderColor: "secondary.light" },
      }}
    >
      {/* ==================== HEADER ==================== */}
      <Stack direction="row" spacing={1} alignItems="flex-start">
        {/* Left: type chip + status chip + canonical + scope + impact_type + date */}
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ flex: 1, minWidth: 0 }}
        >
          <Chip
            label="Impact"
            color="secondary"
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
          {canonicalText && (
            <Chip
              label={canonicalText}
              size="small"
              color="secondary"
              variant="outlined"
              sx={{ fontSize: "0.68rem", height: 20 }}
            />
          )}
          {scopeCfg && (
            <Chip
              label={scopeCfg.label}
              size="small"
              color={scopeCfg.color}
              variant="outlined"
              sx={{ fontSize: "0.68rem", height: 20 }}
            />
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
            <Tooltip title="Validate impact">
              <IconButton
                size="small"
                color="success"
                onClick={handleValidate}
                aria-label="Validate impact"
              >
                <CheckCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          {isPending && (
            <Tooltip title="Reject impact">
              <IconButton
                size="small"
                color="error"
                onClick={handleReject}
                aria-label="Reject impact"
              >
                <CloseCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          <IconButton
            size="small"
            onClick={handleMenuOpen}
            aria-label="Impact actions"
            aria-controls={menuAnchor ? "impact-action-menu" : undefined}
            aria-haspopup="true"
            aria-expanded={Boolean(menuAnchor)}
          >
            <MoreOutlined style={{ fontSize: 16 }} />
          </IconButton>

          <Menu
            id="impact-action-menu"
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
                  <span>Edit impact</span>
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
                <span>Delete impact</span>
              </Stack>
            </MenuItem>
          </Menu>
        </Stack>
      </Stack>

      {/* ==================== BODY: Summary ==================== */}
      {impact.summary && (
        <Typography
          variant="body2"
          fontWeight={600}
          sx={{
            mt: 1.25,
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {impact.summary}
        </Typography>
      )}

      {/* ==================== TYPE-SPECIFIC DETAIL (shared block) ==================== */}
      {/*
        impact_type, metric_text and human_impact are rendered by the shared
        ImpactDetailBlock so the drawer and this card show them identically.
      */}
      <Box sx={{ mt: 1.25 }}>
        <ImpactDetailBlock signal={impact} />
      </Box>

      {/* ==================== SOURCE LINE ==================== */}
      {sourceLine && (
        <>
          <Divider sx={{ mt: 1.5, mb: 1 }} />
          <Typography variant="caption" color="text.disabled">
            {sourceLine}
          </Typography>
        </>
      )}

      {/* ==================== CONFIRM: Delete Impact ==================== */}
      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Delete this impact?"
        message="This impact will be deleted permanently."
        confirmLabel="Delete impact"
        onConfirm={handleDeleteConfirm}
        onClose={() => setConfirmDeleteOpen(false)}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

ImpactCard.propTypes = {
  impact: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string,
    // Canonical axes
    what: PropTypes.string,
    dimension: PropTypes.string,
    // Scope
    scope_level: PropTypes.oneOf(["BUSINESS", "DEPARTMENT", "PERSONAL"]),
    // Impact-specific fields
    impact_type: PropTypes.string,
    human_impact: PropTypes.string,
    metric_text: PropTypes.string,
    // Descriptive
    summary: PropTypes.string,
    notes: PropTypes.string,
    source_quote: PropTypes.string,
    // Source
    source_activity: PropTypes.object,
    // Audit
    created_at: PropTypes.string,
  }).isRequired,
  choices: PropTypes.object,

  /** Lifecycle actions — signature matches SignalCard / PainCard / ObjectiveCard / TechStackCard */
  onValidate: PropTypes.func.isRequired,
  onReject: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
};
