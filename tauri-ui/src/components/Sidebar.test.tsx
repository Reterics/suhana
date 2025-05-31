import { render, screen, fireEvent } from '@testing-library/preact';
import { describe, it, expect, vi } from 'vitest';
import Sidebar from './Sidebar';

// Mock icons (lucide-preact)
vi.mock('lucide-preact', () => ({
  Plus: () => <span data-testid="icon-plus" />,
  X: () => <span data-testid="icon-x" />,
  __esModule: true,
}));

const conversations = [
  { id: 'c1', title: 'First', created: '', last_updated: '' },
  { id: 'c2', title: 'Second', created: '', last_updated: '' },
  { id: 'c3', title: '', created: '', last_updated: '' }, // Should show id
];

describe('Sidebar', () => {
  it('renders conversations and new button', () => {
    render(<Sidebar conversations={conversations} />);
    expect(screen.getByText('Conversations')).toBeTruthy();
    expect(screen.getByText('New')).toBeTruthy();

    // Conversations are rendered in reverse order
    expect(screen.getByText('Second')).toBeTruthy();
    expect(screen.getByText('First')).toBeTruthy();
    // c3 has no title: should show truncated id
    expect(screen.getByText('c3')).toBeTruthy();
  });

  it('renders version and logo', () => {
    render(<Sidebar conversations={[]} />);
    expect(screen.getByText(/v0.1/i)).toBeTruthy();
    expect(screen.getByAltText(/Suhana/i)).toBeTruthy();
  });

  it('calls toggle on X button', () => {
    const toggle = vi.fn();
    render(<Sidebar conversations={[]} toggle={toggle} />);
    fireEvent.click(screen.getByTestId('icon-x').parentElement!);
    expect(toggle).toHaveBeenCalled();
  });

  it('hides sidebar when hidden prop is true', () => {
    const { container } = render(<Sidebar conversations={[]} hidden />);
    // Should have width 0 and overflow hidden
    expect(container.querySelector('aside')!.className).toMatch(/w-0/);
    expect(container.querySelector('aside')!.className).toMatch(/overflow-hidden/);
  });

  it('calls onSelectConversation with new id on New', () => {
    const onSelect = vi.fn();
    render(<Sidebar conversations={[]} onSelectConversation={onSelect} />);
    fireEvent.click(screen.getByText('New'));
    expect(onSelect).toHaveBeenCalledWith(expect.stringMatching(/^id\d+/));
  });

  it('calls onSelectConversation with correct id when conversation is clicked', () => {
    const onSelect = vi.fn();
    render(<Sidebar conversations={conversations} onSelectConversation={onSelect} />);
    // Because the conversations are reversed
    const secondBtn = screen.getByText('Second');
    fireEvent.click(secondBtn);
    expect(onSelect).toHaveBeenCalledWith('c2');

    const firstBtn = screen.getByText('First');
    fireEvent.click(firstBtn);
    expect(onSelect).toHaveBeenCalledWith('c1');
    // No title: id button
    const idBtn = screen.getByText('c3');
    fireEvent.click(idBtn);
    expect(onSelect).toHaveBeenCalledWith('c3');
  });

  it('renders nothing if conversations is empty except New', () => {
    render(<Sidebar conversations={[]} />);
    expect(screen.getByText('New')).toBeTruthy();
    // No conversation button
    expect(screen.queryByRole('button', { name: 'First' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Second' })).toBeNull();
  });
});
