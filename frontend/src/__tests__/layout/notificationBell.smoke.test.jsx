// frontend/src/__tests__/layout/notificationBell.smoke.test.jsx
//
// Compile guard: the notification bell (index.jsx) is not render-tested (Popper
// + custom theme), so at least prove the module and its whole import graph
// (NotificationRow, the respond wiring) load without error.

import { describe, it, expect, vi } from 'vitest';

// The bell -> MainCard -> theme-config pulls a next/font call at module load.
vi.mock('next/font/google', () => ({
  Public_Sans: () => ({ className: 'mock-public-sans', style: { fontFamily: 'mock' } }),
}));

import Notification from 'layout/DashboardLayout/Header/HeaderContent/Notification';

describe('Notification bell (compile guard)', () => {
  it('module loads and exports a component', () => {
    expect(typeof Notification).toBe('function');
  });
});
