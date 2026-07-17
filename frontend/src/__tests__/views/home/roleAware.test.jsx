// frontend/src/__tests__/views/home/roleAware.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

// ==============================|| MOCKS ||============================== //

// Drive the switch by role. Each test sets the return value.
const useUserPermissionsMock = vi.fn(() => ({ isManager: false, isAdmin: false }));
vi.mock('hooks/useUserPermissions', () => ({
  useUserPermissions: () => useUserPermissionsMock(),
}));

// Stub the heavy children so the test isolates the role switch, not their data.
vi.mock('views/home/RepHome', () => ({ default: () => <div>REP_HOME</div> }));
vi.mock('views/home/ManagerHome', () => ({ default: () => <div>MANAGER_HOME</div> }));

// ==============================|| IMPORTS (after mocks) ||============================== //

import HomePage from 'views/home';

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe('HomePage role-aware switch', () => {
  it('renders the rep Home for an individual', () => {
    useUserPermissionsMock.mockReturnValue({ isManager: false, isAdmin: false });
    render(<HomePage />);
    expect(screen.getByText('REP_HOME')).toBeInTheDocument();
    expect(screen.queryByText('MANAGER_HOME')).not.toBeInTheDocument();
  });

  it('renders the manager Home for a manager', () => {
    useUserPermissionsMock.mockReturnValue({ isManager: true, isAdmin: false });
    render(<HomePage />);
    expect(screen.getByText('MANAGER_HOME')).toBeInTheDocument();
    expect(screen.queryByText('REP_HOME')).not.toBeInTheDocument();
  });

  it('renders the manager Home for an admin', () => {
    useUserPermissionsMock.mockReturnValue({ isManager: false, isAdmin: true });
    render(<HomePage />);
    expect(screen.getByText('MANAGER_HOME')).toBeInTheDocument();
  });
});
