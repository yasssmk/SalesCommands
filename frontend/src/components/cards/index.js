// frontend/src/components/cards/index.js
/**
 * Card Components Index
 * 
 * Reusable card components for displaying entities throughout the application.
 * 
 * Components:
 * - RemovableCard: Base card with hover-reveal remove button
 * - InfoItem: Compact info display with icon and label
 * - UserCard: Internal user display (owner, invited users)
 * - ContactCard: External contact display
 * - ActivityMiniCard: Activity summary card (previous/next, linked)
 */

// Base components
export { default as RemovableCard } from './RemovableCard';
export { default as InfoItem } from './InfoItem';

// Entity cards
export { default as UserCard } from './UserCard';
export { default as ContactCard } from './ContactCard';
export { default as ActivityMiniCard } from './ActivityMiniCard';

// Legacy component (kept for backwards compatibility)
export { default as ComponentHeader } from './ComponentHeader';