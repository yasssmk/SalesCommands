// frontend/src/components/tree/GenericTreeView.jsx

import PropTypes from 'prop-types';
import { useState, useMemo, useCallback } from 'react';

// material-ui
import { useTheme, alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';

// mui x tree view
import { RichTreeView } from '@mui/x-tree-view/RichTreeView';

// icons
import { DownOutlined, RightOutlined } from '@ant-design/icons';

/**
 * GenericTreeView - Composant réutilisable pour données hiérarchiques
 */
function GenericTreeView({
  data,
  selectedId,
  onSelect,
  defaultExpandedIds = [],
  onExpand,
  searchTerm = '',
  filterFunction,
  height = '600px',
  maxHeight = '800px',
}) {
  const theme = useTheme();
  const [expandedIds, setExpandedIds] = useState(defaultExpandedIds);

  // ==================== HANDLERS ====================

 const handleSelectChange = useCallback((event, nodeId) => {
  if (!nodeId) return;
  const node = findNodeById(data, nodeId);
  if (node && onSelect) {
    onSelect(nodeId, node);
  }
}, [data, onSelect]);

  const handleExpandedItemsChange = useCallback((event, nodeIds) => {
    setExpandedIds(nodeIds);
    if (onExpand) onExpand(nodeIds);
  }, [onExpand]);

  // ==================== FILTERING ====================

  const filteredData = useMemo(() => {
    if (!searchTerm || searchTerm.trim() === '') return data;
    const filter = filterFunction || defaultFilterFunction;
    return filterTree(data, (node) => filter(node, searchTerm));
  }, [data, searchTerm, filterFunction]);

  const autoExpandedIds = useMemo(() => {
    if (!searchTerm || searchTerm.trim() === '') return expandedIds;
    const ids = new Set(expandedIds);
    const addParentIds = (nodes) => {
      nodes.forEach(node => {
        if (node.children && node.children.length > 0) {
          ids.add(node.id);
          addParentIds(node.children);
        }
      });
    };
    addParentIds(filteredData);
    return Array.from(ids);
  }, [filteredData, searchTerm, expandedIds]);

  // ==================== EMPTY STATE ====================

  if (!filteredData || filteredData.length === 0) {
    return (
      <Box
        sx={{
          height,
          maxHeight,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 3,
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 1
        }}
      >
        <Typography variant="body2" color="text.secondary">
          {searchTerm ? `No results for "${searchTerm}"` : 'No data available'}
        </Typography>
      </Box>
    );
  }

  // ==================== MAIN ====================

  return (
    <Box
      sx={{
        height,
        maxHeight,
        overflow: 'auto',
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 1,
        p: 1
      }}
    >
      <RichTreeView
        id="generic-tree-view"
        items={filteredData}
        selectedItems={selectedId}
        onSelectedItemsChange={handleSelectChange}
        expandedItems={autoExpandedIds}
        onExpandedItemsChange={handleExpandedItemsChange}
        slots={{
            collapseIcon: DownOutlined,
            expandIcon: RightOutlined
        }}
        getItemLabel={(item) => item.name}
        />
    </Box>
  );
}

// ==================== UTILITIES ====================

function findNodeById(nodes, id) {
  for (const node of nodes) {
    if (node.id === id) return node;
    if (node.children) {
      const found = findNodeById(node.children, id);
      if (found) return found;
    }
  }
  return null;
}

function defaultFilterFunction(node, searchTerm) {
  return node.name.toLowerCase().includes(searchTerm.toLowerCase());
}

function filterTree(nodes, filterFn) {
  return nodes.reduce((acc, node) => {
    const matches = filterFn(node);
    const filteredChildren = node.children ? filterTree(node.children, filterFn) : [];
    if (matches || filteredChildren.length > 0) {
      acc.push({ ...node, children: filteredChildren });
    }
    return acc;
  }, []);
}

// ==================== PROP TYPES ====================

GenericTreeView.propTypes = {
  data: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    children: PropTypes.array
  })).isRequired,
  selectedId: PropTypes.string,
  onSelect: PropTypes.func,
  defaultExpandedIds: PropTypes.arrayOf(PropTypes.string),
  onExpand: PropTypes.func,
  searchTerm: PropTypes.string,
  filterFunction: PropTypes.func,
  height: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  maxHeight: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
};

export default GenericTreeView;