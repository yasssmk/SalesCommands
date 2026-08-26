// frontend/src/components/cards/signals/PainCard.jsx
/**
 * PainCard — display card for a single PainSignal.
 *
 * Used by SignalList when signalType === 'pain', in place of the generic
 * SignalCard (which is kept for People / Objective / TechStack).
 *
 * Responsibilities:
 *   - Render Pain header (type chip, status chip, creation date, actions)
 *   - Render Pain body (canonical chip, summary, source provenance line)
 *   - Render the Pain type-specific detail via the shared PainDetailBlock
 *   - Surface lifecycle actions (validate, reject) same as SignalCard
 *   - Confirm destructive action (delete pain)
 *
 * Contract — the parent (AccountSignalsTab / ActivitySignalsTab) owns:
 *   - SignalEditDialog opening for Pain edit (reuses existing flow)
 *   - API calls for validate / reject / delete pain
 *
 * PainCard only emits callbacks; it never calls the API directly.
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

// Shared per-type detail block — single rendering of pain-specific fields
import PainDetailBlock from "components/signals/detail/PainDetailBlock";

// ==============================|| STATUS CONFIG ||============================== //

const STATUS_CONFIG = {
  PENDING: { color: "warning", label: "Pending" },
  VALIDATED: { color: "success", label: "Validated" },
  REJECTED: { color: "error", label: "Rejected" },
};

// ==============================|| HELPERS ||============================== //

function formatContact(contact) {
  if (!contact) return null;
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  return name || null;
}

/**
 * Resolve a choices-array label by value.
 */
function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

// ==============================|| CONFIRM DIALOG ||============================== //

/**
 * Minimal inline confirm dialog for the Pain delete action.
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

// ==============================|| PAIN CARD ||============================== //

/**
 * PainCard
 *
 * @param {Object}   pain             - PainSignal
 * @param {Object}   choices          - From useGetSignalChoices()
 * @param {Function} onValidate       - (pain, 'pain') => void
 * @param {Function} onReject         - (pain, 'pain') => void
 * @param {Function} onEdit           - (pain, 'pain') => void — opens SignalEditDialog
 * @param {Function} onDelete         - (pain, 'pain') => void — parent handles API
 */
export default function PainCard({
  pain,
  choices,
  onValidate,
  onReject,
  onEdit,
  onDelete,
}) {
  // ==============================|| LOCAL STATE ||============================== //

  const [menuAnchor, setMenuAnchor] = useState(null);
  const [confirmDeletePainOpen, setConfirmDeletePainOpen] = useState(false);

  // ==============================|| DERIVED ||============================== //

  const status = pain.status ?? "PENDING";
  const statusCfg = STATUS_CONFIG[status] ?? {
    color: "default",
    label: status,
  };

  const isPending = status === "PENDING";

  const createdDate = pain.created_at
    ? new Date(pain.created_at).toLocaleDateString(undefined, {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : null;

  /** Canonical axes chip text — "Operations × Time" */
  // choices.signal_whats / signal_dimensions expose the shared
  // canonical-axis enums. Pain's `what` and `dimension`
  // model fields are unchanged — only the source of display labels
  // differs. Same applies when a Pain is rendered inside a cluster.
  const canonicalText = useMemo(() => {
    const whatLabel = resolveLabel(choices?.signal_whats, pain.what);
    const dimensionLabel = resolveLabel(
      choices?.signal_dimensions,
      pain.dimension,
    );
    if (!whatLabel || !dimensionLabel) return null;
    return `${whatLabel} × ${dimensionLabel}`;
  }, [choices, pain.what, pain.dimension]);

  /** Source line */
  const sourceLine = useMemo(() => {
    const contactName = formatContact(pain.source_contact);
    const activity = pain.source_activity;
    const rawDate = activity?.scheduled_date || activity?.completed_at;
    let dateStr = "";
    if (rawDate) {
      try {
        dateStr = new Date(rawDate).toISOString().slice(0, 10);
      } catch {
        dateStr = String(rawDate).slice(0, 10);
      }
    }

    if (contactName && dateStr) {
      return `Reported by ${contactName} · ${dateStr}`;
    }
    if (contactName) return `Reported by ${contactName}`;
    if (dateStr) return dateStr;
    return null;
  }, [pain.source_contact, pain.source_activity]);

  // ==============================|| MENU HANDLERS ||============================== //

  const handleMenuOpen = useCallback((e) => {
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
  }, []);

  const handleMenuClose = useCallback(() => setMenuAnchor(null), []);

  const handleEditPain = useCallback(() => {
    handleMenuClose();
    onEdit(pain, "pain");
  }, [handleMenuClose, onEdit, pain]);

  const handleDeletePainRequest = useCallback(() => {
    handleMenuClose();
    setConfirmDeletePainOpen(true);
  }, [handleMenuClose]);

  const handleDeletePainConfirm = useCallback(() => {
    setConfirmDeletePainOpen(false);
    onDelete(pain, "pain");
  }, [onDelete, pain]);

  const handleValidate = useCallback(() => {
    onValidate(pain, "pain");
  }, [onValidate, pain]);

  const handleReject = useCallback(() => {
    onReject(pain, "pain");
  }, [onReject, pain]);

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
        "&:hover": { borderColor: "primary.light" },
      }}
    >
      {/* ==================== HEADER ==================== */}
      <Stack direction="row" spacing={1} alignItems="flex-start">
        {/* Left: type chip + status chip + canonical + date */}
        <Stack
          direction="row"
          spacing={0.75}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ flex: 1, minWidth: 0 }}
        >
          <Chip
            label="Pain"
            color="error"
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
              color="error"
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
            <Tooltip title="Validate pain">
              <IconButton
                size="small"
                color="success"
                onClick={handleValidate}
                aria-label="Validate pain"
              >
                <CheckCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          {isPending && (
            <Tooltip title="Reject pain">
              <IconButton
                size="small"
                color="error"
                onClick={handleReject}
                aria-label="Reject pain"
              >
                <CloseCircleOutlined style={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}

          <IconButton
            size="small"
            onClick={handleMenuOpen}
            aria-label="Pain actions"
            aria-controls={menuAnchor ? "pain-action-menu" : undefined}
            aria-haspopup="true"
            aria-expanded={Boolean(menuAnchor)}
          >
            <MoreOutlined style={{ fontSize: 16 }} />
          </IconButton>

          <Menu
            id="pain-action-menu"
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={handleMenuClose}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            transformOrigin={{ vertical: "top", horizontal: "right" }}
          >
            {status !== "REJECTED" && (
              <MenuItem onClick={handleEditPain} dense>
                <Stack direction="row" spacing={1} alignItems="center">
                  <EditOutlined style={{ fontSize: 14 }} />
                  <span>Edit pain</span>
                </Stack>
              </MenuItem>
            )}
            <MenuItem
              onClick={handleDeletePainRequest}
              dense
              sx={{ color: "error.main" }}
            >
              <Stack direction="row" spacing={1} alignItems="center">
                <DeleteOutlined style={{ fontSize: 14 }} />
                <span>Delete pain</span>
              </Stack>
            </MenuItem>
          </Menu>
        </Stack>
      </Stack>

      {/* ==================== BODY: Summary ==================== */}
      {pain.summary && (
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
          {pain.summary}
        </Typography>
      )}

      {/* ==================== TYPE-SPECIFIC DETAIL (shared block) ==================== */}
      {/*
        related_techstack_mention is rendered by the shared PainDetailBlock so
        the drawer and this card match.
      */}
      <Box sx={{ mt: 1 }}>
        <PainDetailBlock signal={pain} />
      </Box>

      {/* ==================== SOURCE LINE ==================== */}
      {sourceLine && (
        <Typography
          variant="caption"
          color="text.disabled"
          display="block"
          sx={{ mt: 0.75 }}
        >
          {sourceLine}
        </Typography>
      )}

      {/* ==================== CONFIRM: Delete Pain ==================== */}
      <ConfirmDialog
        open={confirmDeletePainOpen}
        title="Delete this pain?"
        message="This pain will be deleted permanently."
        confirmLabel="Delete pain"
        onConfirm={handleDeletePainConfirm}
        onClose={() => setConfirmDeletePainOpen(false)}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

PainCard.propTypes = {
  pain: PropTypes.shape({
    id: PropTypes.string.isRequired,
    status: PropTypes.string,
    what: PropTypes.string,
    dimension: PropTypes.string,
    summary: PropTypes.string,
    source_contact: PropTypes.object,
    source_activity: PropTypes.object,
    created_at: PropTypes.string,
    /** Optional free-text tool cross-reference. */
    related_techstack_mention: PropTypes.string,
  }).isRequired,
  choices: PropTypes.object,

  /** Lifecycle actions — signature matches SignalCard for AccountSignalsTab compatibility */
  onValidate: PropTypes.func.isRequired,
  onReject: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
};
