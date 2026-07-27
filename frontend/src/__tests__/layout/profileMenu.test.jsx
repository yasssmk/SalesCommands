// frontend/src/__tests__/layout/profileMenu.test.jsx
//
// The header profile dropdown is reduced to "My Objectives" (-> /objectives) and
// "Logout"; the dead entries are gone. Real render of ProfileTab; only
// next/navigation is mocked to capture the route push.

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

const push = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));

import ProfileTab from 'layout/DashboardLayout/Header/HeaderContent/Profile/ProfileTab';

afterEach(() => {
  cleanup();
  push.mockClear();
});

describe('ProfileTab (header dropdown)', () => {
  it('keeps only My Objectives and Logout; dead entries removed', () => {
    render(<ProfileTab handleLogout={vi.fn()} />);
    expect(screen.getByText('My Objectives')).toBeTruthy();
    expect(screen.getByText('Logout')).toBeTruthy();
    ['Edit Profile', 'View Profile', 'Social Profile', 'Billing', 'Setting'].forEach((dead) => {
      expect(screen.queryByText(dead)).toBeNull();
    });
  });

  it('My Objectives navigates to /objectives', () => {
    render(<ProfileTab handleLogout={vi.fn()} />);
    fireEvent.click(screen.getByText('My Objectives'));
    expect(push).toHaveBeenCalledWith('/objectives');
  });

  it('Logout calls the handler', () => {
    const handleLogout = vi.fn();
    render(<ProfileTab handleLogout={handleLogout} />);
    fireEvent.click(screen.getByText('Logout'));
    expect(handleLogout).toHaveBeenCalledTimes(1);
  });
});
