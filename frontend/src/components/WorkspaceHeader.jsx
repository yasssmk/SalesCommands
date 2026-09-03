// frontend/src/components/WorkspaceHeader.jsx
//
// HEADER-1 — the new SHARED workspace header, themed via aphoriQ, designed to
// replace WorkspaceLayout's header progressively across surfaces. It is a
// STRUCTURE with OPAQUE slots — each surface fills them differently, the shell
// imposes nothing on their content:
//
//   Row 1 : [ avatar · title (editable?) · headerActions ]
//   Row 2 : [ chips ]
//   extraRows? (optional nodes)
//   ── hairline filet ──  (only when there are infoItems)
//   infoItems (the info row)
//
// Slots: avatar (node) · title (string) + onTitleSave? + titleDisabled? ·
//        headerActions (node) · chips (array<node>) · extraRows? (array<node>) ·
//        infoItems (array<node>). No MainCard, no styled(), no hardcoded hex/px —
//        weights/colours/radii/borders come from the theme.

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Primitives
import Surface from "components/display/Surface";
import EditableField from "sections/accounts/workspace/EditableField";

// ==============================|| WORKSPACE HEADER ||============================== //

export default function WorkspaceHeader({
  avatar,
  title,
  onTitleSave,
  titleDisabled = false,
  headerActions,
  chips,
  extraRows,
  infoItems,
}) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  const validChips = (chips || []).filter(Boolean);
  const validExtraRows = (extraRows || []).filter(Boolean);
  const validInfoItems = (infoItems || []).filter(Boolean);

  return (
    <Surface level="level1" radius="lg" data-testid="workspace-header" sx={{ p: 2.5, mb: 2 }}>
      <Stack spacing={1.5}>
        {/* Row 1 — avatar · title · actions */}
        <Stack direction="row" alignItems="center" spacing={2} sx={{ flexWrap: "wrap" }}>
          {avatar}

          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            {onTitleSave ? (
              <EditableField
                value={title}
                fieldKey="title"
                onSave={onTitleSave}
                placeholder="Untitled…"
                variant="h3"
                // Bold weight comes from the theme's token, never a literal.
                typographyProps={{ component: "h1", noWrap: true, sx: { fontWeight: "bold" } }}
                disabled={titleDisabled}
              />
            ) : (
              <Typography variant="h3" component="h1" noWrap sx={{ fontWeight: "bold" }}>
                {title}
              </Typography>
            )}
          </Box>

          {headerActions}
        </Stack>

        {/* Row 2 — chips */}
        {validChips.length > 0 && (
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            {validChips}
          </Stack>
        )}

        {/* Extra rows (optional) */}
        {validExtraRows.map((row, index) => (
          <Box key={index}>{row}</Box>
        ))}

        {/* Hairline filet — only when there is an info row below it */}
        {validInfoItems.length > 0 && (
          <>
            <Box
              data-testid="header-rule"
              sx={{
                borderTopStyle: "solid",
                borderTopWidth: aq.border.width.hairline,
                borderTopColor: aq.border.color,
              }}
            />
            <Stack direction="row" spacing={3} alignItems="center" flexWrap="wrap" useFlexGap>
              {validInfoItems}
            </Stack>
          </>
        )}
      </Stack>
    </Surface>
  );
}

WorkspaceHeader.propTypes = {
  /** Pre-built avatar node for Row 1 (opaque). */
  avatar: PropTypes.node,
  /** Title text for Row 1. */
  title: PropTypes.string,
  /** If provided, the title becomes editable via EditableField. */
  onTitleSave: PropTypes.func,
  /** Disable title editing (only relevant with onTitleSave). */
  titleDisabled: PropTypes.bool,
  /** Actions node rendered top-right of Row 1 (opaque, e.g. a ⋮ menu). */
  headerActions: PropTypes.node,
  /** Array of chip nodes for Row 2 (opaque). */
  chips: PropTypes.arrayOf(PropTypes.node),
  /** Extra row nodes between chips and the filet (opaque). */
  extraRows: PropTypes.arrayOf(PropTypes.node),
  /** Array of info-row nodes after the filet (opaque). */
  infoItems: PropTypes.arrayOf(PropTypes.node),
};
