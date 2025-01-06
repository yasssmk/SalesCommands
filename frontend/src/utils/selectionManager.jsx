import { useState, useCallback, useMemo } from 'react';

export const useSelectionManager = (initialSelection = []) => {
  const [selectedItems, setSelectedItems] = useState(new Set(initialSelection));

  // Memoized count of selected items
  const selectedCount = useMemo(() => selectedItems.size, [selectedItems]);

  // Toggle single item selection
  const toggleSelection = useCallback((item) => {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      if (next.has(item.id)) {
        next.delete(item.id);
      } else {
        next.add(item.id);
      }
      return next;
    });
  }, []);

  // Toggle all items selection
  const toggleSelectAll = useCallback((items, isSelected) => {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      items.forEach((item) => {
        if (isSelected) {
          next.add(item.id);
        } else {
          next.delete(item.id);
        }
      });
      return next;
    });
  }, []);

  // Check if a specific item is selected
  const isSelected = useCallback(
    (item) => selectedItems.has(item.id),
    [selectedItems]
  );

  // Get all selected items data
  const getSelectedItems = useCallback(
    (allItems) => allItems.filter((item) => selectedItems.has(item.id)),
    [selectedItems]
  );

  // Clear all selections
  const clearSelection = useCallback(() => {
    setSelectedItems(new Set());
  }, []);

  const setSelectedItemsDirectly = useCallback((items) => {
    setSelectedItems(new Set(items));
  }, []);

  return {
    selectedItems,
    selectedCount,
    toggleSelection,
    toggleSelectAll,
    isSelected,
    getSelectedItems,
    clearSelection,
    setSelectedItems: setSelectedItemsDirectly
  };
};