'use client';
import { useState, useRef } from 'react';
import PropTypes from 'prop-types';

// material-ui
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// third-party
import { CSVLink } from 'react-csv';

// project imports
import IconButton from 'components/@extended/IconButton';

// assets
import EditOutlined from '@ant-design/icons/EditOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import MoreOutlined from '@ant-design/icons/MoreOutlined';
import DownloadOutlined from '@ant-design/icons/DownloadOutlined';
import UploadOutlined from '@ant-design/icons/UploadOutlined';

// ==============================|| TABLE HEADER ACTIONS ||============================== //

export default function TableHeaderActions({
  selectedRowCount = 0,
  onEdit,
  onDelete,
  onImport,
  exportData = [],
  exportHeaders = [],
  exportFilename = 'export.csv'
}) {
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState(null);
  const csvLinkRef = useRef(null);
  const open = Boolean(anchorEl);

  const handleMenuClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleExportClick = () => {
    // Trigger CSV download
    if (csvLinkRef.current) {
      csvLinkRef.current.link.click();
    }
    handleMenuClose();
  };

  // Handler Import CSV
  const handleImportClick = () => {
      handleMenuClose();
      if (onImport) {
        onImport();
      }
    };


  return (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
      {/* Edit Button - Visible only when rows are selected */}
      {selectedRowCount > 0 && (
        <Tooltip title={`Edit ${selectedRowCount} selected`}>
          <IconButton
            color="secondary"
            onClick={(e) => {
              e.stopPropagation();
              if (onEdit) {
                onEdit();
              }
            }}
          >
            <EditOutlined />
          </IconButton>
        </Tooltip>
      )}

      {/* Delete Button - Visible only when rows are selected */}
      {selectedRowCount > 0 && (
        <Tooltip title={`Delete ${selectedRowCount} selected`}>
          <IconButton
            color="secondary"
            onClick={(e) => {
              e.stopPropagation();
              if (onDelete) {
                onDelete();
              }
            }}
          >
            <DeleteOutlined />
          </IconButton>
        </Tooltip>
      )}

      {/* More Menu Button - Always visible */}
      <Tooltip title="More actions">
        <IconButton
          color="secondary"
          onClick={handleMenuClick}
          aria-controls={open ? 'table-actions-menu' : undefined}
          aria-haspopup="true"
          aria-expanded={open ? 'true' : undefined}
        >
          <MoreOutlined style={{ fontSize: '20px' }} />
        </IconButton>
      </Tooltip>

      {/* Hidden CSV Link */}
      <CSVLink
        data={exportData}
        headers={exportHeaders}
        filename={exportFilename}
        ref={csvLinkRef}
        style={{ display: 'none' }}
      />

      {/* Dropdown Menu */}
      <Menu
        id="table-actions-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleMenuClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right'
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right'
        }}
      >
        {/* Export CSV */}
        <MenuItem onClick={handleExportClick} sx={{ py: 1 }}>
          <ListItemIcon>
            <UploadOutlined style={{ fontSize: '16px', color: theme.palette.text.secondary }} />
          </ListItemIcon>
          <ListItemText>
            <Typography variant="h6" color="text.secondary">Export CSV</Typography>
          </ListItemText>
        </MenuItem>

        <Divider />

        {/* Import CSV */}
        <MenuItem onClick={handleImportClick} sx={{ py: 1 }}>
          <ListItemIcon>
            <DownloadOutlined style={{ fontSize: '18px', color: theme.palette.text.secondary }} />
          </ListItemIcon>
          <ListItemText>
            <Typography variant="h6" color="text.secondary">Import CSV</Typography>
          </ListItemText>
        </MenuItem>
      </Menu>
    </Box>
  );
}

TableHeaderActions.propTypes = {
  selectedRowCount: PropTypes.number,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
  onImport: PropTypes.func,
  exportData: PropTypes.array,
  exportHeaders: PropTypes.array,
  exportFilename: PropTypes.string
};