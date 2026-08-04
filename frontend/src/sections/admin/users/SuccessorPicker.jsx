// frontend/src/sections/admin/users/SuccessorPicker.jsx

import PropTypes from 'prop-types';
import React, { useEffect, useRef } from 'react';

// material-ui
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// project imports
import AsyncUserSelect from 'components/AsyncSelection/AsyncUserSelect';
import { useDeactivationPreview } from 'api/admin/users';

/**
 * Shared successor-choice UI for user deactivation.
 *
 * Deactivating a user requires a successor (server-enforced). This component is
 * reused by BOTH entry points (the edit-modal switch and the list row action)
 * so they present exactly the same window.
 *
 * - shows a light recap of what will transfer (deals / accounts / activities),
 * - lets the admin pick the successor: ONLY active users, NEVER the person
 *   being deactivated,
 * - pre-fills with the person's active direct team manager when the backend
 *   suggests one; otherwise the field stays empty and the admin chooses.
 *
 * `value` / `onChange(event, newValue)` are controlled by the parent.
 */
function SuccessorPicker({ targetUser, value, onChange, disabled = false }) {
  const targetId = targetUser?.id;
  const { preview, previewLoading } = useDeactivationPreview(targetId, Boolean(targetId));

  const counts = preview?.counts || { deals: 0, accounts: 0, activities: 0 };
  const suggested = preview?.suggested_successor || null;

  // Pre-fill with the suggested successor once, only if the admin hasn't picked.
  const prefilled = useRef(false);
  useEffect(() => {
    if (prefilled.current) return;
    if (!value && suggested) {
      prefilled.current = true;
      onChange?.(null, suggested);
    }
  }, [suggested, value, onChange]);

  // Never offer the person being deactivated, even though they are still active.
  const excludeSelf = (options) =>
    (options || []).filter((o) => String(o?.id) !== String(targetId));

  return (
    <Box sx={{ mt: 1 }}>
      <Alert severity="warning" sx={{ mb: 2 }}>
        Deactivating this user removes their access immediately and frees their seat.
        Their open deals, prospect accounts and pending deal activities are transferred
        to the successor below; their campaigns are cancelled. This cannot be
        automatically undone.
      </Alert>

      <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
        <Chip size="small" variant="outlined"
          label={`${counts.deals} deal${counts.deals === 1 ? '' : 's'}`} />
        <Chip size="small" variant="outlined"
          label={`${counts.accounts} account${counts.accounts === 1 ? '' : 's'}`} />
        <Chip size="small" variant="outlined"
          label={`${counts.activities} activit${counts.activities === 1 ? 'y' : 'ies'}`} />
        <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
          will be transferred
        </Typography>
      </Stack>

      <AsyncUserSelect
        value={value || null}
        onChange={onChange}
        label="Successor"
        placeholder="Search an active user…"
        disabled={disabled || previewLoading}
        filters={{ is_active: true }}
        filterOptions={excludeSelf}
      />
    </Box>
  );
}

SuccessorPicker.propTypes = {
  targetUser: PropTypes.object,
  value: PropTypes.object,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool
};

export default SuccessorPicker;
