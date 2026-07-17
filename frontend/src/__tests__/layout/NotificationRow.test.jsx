// frontend/src/__tests__/layout/NotificationRow.test.jsx

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

// Keep the date formatter trivial and dependency-free.
vi.mock('config/formatters', () => ({ formatDateTime: () => '2026-07-15 10:00' }));

import NotificationRow from 'layout/DashboardLayout/Header/HeaderContent/Notification/NotificationRow';

afterEach(() => cleanup());

const pendingItem = {
  id: 'n1',
  title: 'You were invited to a call',
  body: 'Discovery with Acme',
  created_at: '2026-07-15T10:00:00Z',
  read_at: null,
  response_status: 'PENDING',
};

const informativeItem = {
  id: 'n2',
  title: 'Coaching note added',
  body: 'Nice work',
  created_at: '2026-07-15T10:00:00Z',
  read_at: null,
  response_status: null,
};

describe('NotificationRow', () => {
  it('shows Accept / Decline only for a PENDING invitation', () => {
    render(<NotificationRow item={pendingItem} onClick={vi.fn()} onRespond={vi.fn()} />);
    expect(screen.getByText('Accept')).toBeInTheDocument();
    expect(screen.getByText('Decline')).toBeInTheDocument();
  });

  it('shows no response buttons for an informative notification', () => {
    render(<NotificationRow item={informativeItem} onClick={vi.fn()} onRespond={vi.fn()} />);
    expect(screen.queryByText('Accept')).not.toBeInTheDocument();
    expect(screen.queryByText('Decline')).not.toBeInTheDocument();
  });

  it('responds with the right status and does NOT trigger the row click (stopPropagation)', () => {
    const onClick = vi.fn();
    const onRespond = vi.fn();
    render(<NotificationRow item={pendingItem} onClick={onClick} onRespond={onRespond} />);

    fireEvent.click(screen.getByText('Accept'));
    expect(onRespond).toHaveBeenCalledWith('ACCEPTED');
    expect(onClick).not.toHaveBeenCalled(); // row navigation/mark-read suppressed

    fireEvent.click(screen.getByText('Decline'));
    expect(onRespond).toHaveBeenCalledWith('DECLINED');
    expect(onClick).not.toHaveBeenCalled();
  });

  it('clicking the row itself still fires onClick', () => {
    const onClick = vi.fn();
    render(<NotificationRow item={informativeItem} onClick={onClick} onRespond={vi.fn()} />);
    fireEvent.click(screen.getByText('Coaching note added'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
