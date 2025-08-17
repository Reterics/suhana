import { render, screen, fireEvent } from '@testing-library/preact';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Sidebar from './Sidebar';

// Mock icons (lucide-preact)
vi.mock('lucide-preact', () => ({
  Plus: () => <span data-testid="icon-plus" />,
  X: () => <span data-testid="icon-x" />,
  __esModule: true
}));

// Mock ChatContext to supply conversationList and actions
const mockLoadConversation = vi.fn();
const mockAddConversation = vi.fn();
const baseConversations = [
  { id: 'c1', title: 'First', created: '', last_updated: '' },
  { id: 'c2', title: 'Second', created: '', last_updated: '' },
  { id: 'c3', title: '', created: '', last_updated: '' }
];

vi.mock('../context/ChatContext.tsx', () => ({
  useChat: () => ({
    conversationList: baseConversations,
    loadConversation: mockLoadConversation,
    addConversation: mockAddConversation
  }),
  __esModule: true
}));

describe('Sidebar', () => {
  beforeEach(() => {
    mockLoadConversation.mockReset();
    mockAddConversation.mockReset();
  });

  it('renders conversations and new button', () => {
    render(<Sidebar />);
    expect(screen.getByText('Conversations')).toBeTruthy();
    expect(screen.getByText('New')).toBeTruthy();

    // Conversations are rendered in reverse order
    expect(screen.getByText('Second')).toBeTruthy();
    expect(screen.getByText('First')).toBeTruthy();
    // c3 has no title: should show truncated id slice
    expect(screen.getByText('c3'.slice(0, 8))).toBeTruthy();
  });

  it('renders version and logo', () => {
    render(<Sidebar />);
    expect(screen.getByText(/v0.1/i)).toBeTruthy();
    expect(screen.getByAltText(/Suhana/i)).toBeTruthy();
  });

  it('calls toggle on X button', () => {
    const toggle = vi.fn();
    render(<Sidebar toggle={toggle} />);
    fireEvent.click(screen.getByTestId('icon-x').parentElement!);
    expect(toggle).toHaveBeenCalled();
  });

  it('hides sidebar when hidden prop is true', () => {
    const { container } = render(<Sidebar hidden />);
    expect(container.querySelector('aside')!.className).toMatch(/w-0/);
    expect(container.querySelector('aside')!.className).toMatch(/overflow-hidden/);
  });

  it('calls addConversation on New', () => {
    render(<Sidebar />);
    fireEvent.click(screen.getByText('New'));
    expect(mockAddConversation).toHaveBeenCalled();
  });

  it('calls loadConversation with correct id when conversation is clicked', () => {
    render(<Sidebar />);
    // Because the conversations are reversed, clicking 'Second' still loads 'c2'
    fireEvent.click(screen.getByText('Second'));
    expect(mockLoadConversation).toHaveBeenCalledWith('c2');

    fireEvent.click(screen.getByText('First'));
    expect(mockLoadConversation).toHaveBeenCalledWith('c1');

    // No title: should display id slice, click it and expect 'c3'
    fireEvent.click(screen.getByText('c3'.slice(0, 8)));
    expect(mockLoadConversation).toHaveBeenCalledWith('c3');
  });

  it('renders New button regardless of conversations', async () => {
    render(<Sidebar />);
    expect(screen.getByText('New')).toBeTruthy();
  });
});
