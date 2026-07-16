// frontend/src/sections/home/TeamTodoFilterPanel.jsx

import PropTypes from 'prop-types';

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Drawer from '@mui/material/Drawer';
import FormControl from '@mui/material/FormControl';
import IconButton from '@mui/material/IconButton';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import CloseOutlined from '@ant-design/icons/CloseOutlined';
import FilterOutlined from '@ant-design/icons/FilterOutlined';
import ClearOutlined from '@ant-design/icons/ClearOutlined';

// ==============================|| TEAM TODO FILTER PANEL — the manager's standard filter drawer ||============================== //

/**
 * The standard filter drawer for the manager team todo table (mirrors
 * TerritoryFilterPanel): a Team select over the manager's managed subtree and a
 * Person select over the team's people, with pending -> Apply semantics. Same
 * mechanism as any other table in the app — no bespoke dropdown.
 */
export default function TeamTodoFilterPanel({
  open,
  onClose,
  pendingFilters,
  teamOptions = [],
  personOptions = [],
  onFilterChange,
  onApply,
  onClear,
}) {
  const handleApply = () => {
    onApply?.();
    onClose?.();
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: '100%', sm: 360 } } }}
    >
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <FilterOutlined style={{ fontSize: 20 }} />
          <Typography variant="h5">Filters</Typography>
        </Stack>
        <IconButton onClick={onClose} size="small">
          <CloseOutlined />
        </IconButton>
      </Stack>

      <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2 }}>
        <Stack spacing={2.5}>
          <FormControl fullWidth size="small">
            <InputLabel id="team-todo-filter-team">Team</InputLabel>
            <Select
              labelId="team-todo-filter-team"
              label="Team"
              value={pendingFilters?.team || ''}
              onChange={(e) => onFilterChange('team', e.target.value)}
            >
              <MenuItem value="">All my teams</MenuItem>
              {teamOptions.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth size="small">
            <InputLabel id="team-todo-filter-person">Person</InputLabel>
            <Select
              labelId="team-todo-filter-person"
              label="Person"
              value={pendingFilters?.owner || ''}
              onChange={(e) => onFilterChange('owner', e.target.value)}
            >
              <MenuItem value="">Everyone</MenuItem>
              {personOptions.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
      </Box>

      <Box sx={{ borderTop: 1, borderColor: 'divider', p: 2 }}>
        <Stack direction="row" spacing={1}>
          <Button fullWidth variant="outlined" color="secondary" startIcon={<ClearOutlined />} onClick={onClear}>
            Clear all
          </Button>
          <Button fullWidth variant="contained" onClick={handleApply}>
            Apply
          </Button>
        </Stack>
      </Box>
    </Drawer>
  );
}

TeamTodoFilterPanel.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  pendingFilters: PropTypes.shape({ team: PropTypes.string, owner: PropTypes.string }),
  teamOptions: PropTypes.array,
  personOptions: PropTypes.array,
  onFilterChange: PropTypes.func.isRequired,
  onApply: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
};
