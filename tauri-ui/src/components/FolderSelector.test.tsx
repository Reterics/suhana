import { render, screen, fireEvent, waitFor } from '@testing-library/preact';
import { vi, describe, it, beforeEach, expect } from 'vitest';
import { FolderSelector } from './FolderSelector';

// Mock ChatContext to provide getFolders so component doesn't throw
let mockGetFolders: (path: string) => Promise<any>;
vi.mock('../context/ChatContext.tsx', () => ({
  useChat: () => ({
    getFolders: (path: string) => mockGetFolders(path)
  }),
  __esModule: true
}));

// Mock icons (lucide-preact)
vi.mock('lucide-preact', () => ({
  ChevronUp: () => <span data-testid="icon-up" />,
  ChevronLeft: () => <span data-testid="icon-left" />,
  ChevronRight: () => <span data-testid="icon-right" />,
  X: () => <span data-testid="icon-x" />,
  __esModule: true
}));

const FAKE_RESPONSE = {
  current: '/home/user',
  parent: '/home',
  path_parts: [
    { name: 'Root', path: '' },
    { name: 'home', path: '/home' },
    { name: 'user', path: '/home/user' }
  ],
  subfolders: [
    {
      name: 'projectA',
      path: '/home/user/projectA',
      is_project: true,
      modified: 1720000000
    },
    {
      name: 'docs',
      path: '/home/user/docs',
      is_project: false,
      modified: 1710000000
    }
  ],
  separator: '/',
  recent_projects: ['/home/user/projectA']
};

function setupFetch(resp: Partial<typeof FAKE_RESPONSE> = {}, ok = true) {
  const data = { ...FAKE_RESPONSE, ...resp };
  // Default mockGetFolders will use global fetch so tests can still inspect fetch calls
  mockGetFolders = async (path: string) => {
    const res = (await (globalThis.fetch as any)(`http://test/browse?path=${encodeURIComponent(path)}`)) as any;
    if (res.ok === false) {
      const text = await (res.text ? res.text() : Promise.resolve('Failed to fetch folders'));
      throw new Error(text || 'Failed to fetch folders');
    }
    return res.json();
  };
  globalThis.fetch = vi.fn().mockImplementation(() =>
    Promise.resolve({
      ok,
      json: () => Promise.resolve(data)
    })
  ) as any;
  }

beforeEach(() => {
  vi.clearAllMocks();
  setupFetch();
});

describe('FolderSelector', () => {
  it('renders folders and recent projects with unique test ids', async () => {
    render(<FolderSelector onSelect={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByTestId('folderList')).toBeTruthy();
      expect(screen.getByTestId('recentFolders')).toBeTruthy();
    });

    // Get folder names in grid
    const folderNames = Array.from(
      screen.getByTestId('folderList').querySelectorAll('span.truncate.text-sm')
    ).map(span => span.textContent?.trim());

    expect(folderNames).toContain('projectA');
    expect(folderNames).toContain('docs');

    // Get recent project names
    const recentNames = Array.from(
      screen
        .getByTestId('recentFolders')
        .querySelectorAll('span.truncate.text-sm')
    ).map(span => span.textContent?.trim());

    expect(recentNames).toContain('projectA');
  });

  it('calls onClose when clicking backdrop or X', async () => {
    const onClose = vi.fn();
    render(<FolderSelector onSelect={vi.fn()} onClose={onClose} />);
    // Click backdrop
    fireEvent.click(
      screen.getByText('Select Project Folder').closest('.fixed')!
    );
    expect(onClose).toHaveBeenCalledTimes(1);
    // Click X button
    fireEvent.click(screen.getByTestId('icon-x').parentElement!);
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('navigates by clicking breadcrumb', async () => {
    render(<FolderSelector onSelect={vi.fn()} onClose={vi.fn()} />);
    await screen.findByText('user');
    const breadcrumb = screen.getByText('home');
    fireEvent.click(breadcrumb);
    const calls = (globalThis.fetch as any).mock.calls;
    expect(calls[1][0]).toContain('path=%2Fhome');
  });

  it('navigates to folder and selects on double click (folder list)', async () => {
    const onSelect = vi.fn();
    render(<FolderSelector onSelect={onSelect} onClose={vi.fn()} />);
    // Wait for folders to load and first folder button to appear
    await waitFor(() => {
      const list = screen.getByTestId('folderList');
      expect(list.querySelectorAll('button').length).toBeGreaterThan(0);
    });

    const folderButtons = screen
      .getByTestId('folderList')
      .querySelectorAll('button');

    // Click projectA in folders grid
    fireEvent.click(folderButtons[0]);
    // Wait for fetch to be called again
    await waitFor(() => expect((globalThis.fetch as any).mock.calls.length).toBeGreaterThan(1));

    // Double click to select
    fireEvent.dblClick(folderButtons[0]);
    expect(onSelect).toHaveBeenCalledWith('/home/user/projectA');
  });

  it('navigates to recent project and selects on double click', async () => {
    const onSelect = vi.fn();
    render(<FolderSelector onSelect={onSelect} onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByTestId('recentFolders')).toBeTruthy();
    });
    const recentButtons = screen
      .getByTestId('recentFolders')
      .querySelectorAll('button');
    // Click recent projectA
    fireEvent.click(recentButtons[0]);
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);

    // Double click to select recent projectA
    fireEvent.dblClick(recentButtons[0]);
    expect(onSelect).toHaveBeenCalledWith('/home/user/projectA');
  });

  it('selects folder using Select This Folder button', async () => {
    const onSelect = vi.fn();
    render(<FolderSelector onSelect={onSelect} onClose={vi.fn()} />);
    // Wait until currentPath is set by initial fetch
    const input = await screen.findByTestId('inputPath');
    await waitFor(() => expect((input as HTMLInputElement).getAttribute('value') || (input as HTMLInputElement).value).toBe('/home/user'));
    fireEvent.click(screen.getByTestId('selectFolderButton'));
    expect(onSelect).toHaveBeenCalledWith('/home/user');
  });

  it('shows error if fetch fails', async () => {
    setupFetch({}, false);
    render(<FolderSelector onSelect={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText(/Failed to fetch folders/i)).toBeTruthy();
    });
  });

  it('shows No folders found if empty', async () => {
    setupFetch({ subfolders: [] });
    render(<FolderSelector onSelect={vi.fn()} onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText(/No folders found/i)).toBeTruthy();
    });
  });

  it('handles input path navigation with Enter key', async () => {
    render(<FolderSelector onSelect={vi.fn()} onClose={vi.fn()} />);
    const input = screen.getByTestId('inputPath');
    fireEvent.input(input, { target: { value: '/tmp' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    const calls = (globalThis.fetch as any).mock.calls;
    expect(calls[1][0]).toContain('path=%2Ftmp');
  });

  it('calls onSelect("") when Cancel is clicked', async () => {
    const onSelect = vi.fn();
    render(<FolderSelector onSelect={onSelect} onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onSelect).toHaveBeenCalledWith('');
  });

  it('navigates back and forward with history buttons', async () => {
    render(<FolderSelector onSelect={vi.fn()} onClose={vi.fn()} />);
    // Wait for first folder button to appear
    await waitFor(() => {
      const list = screen.getByTestId('folderList');
      expect(list.querySelectorAll('button').length).toBeGreaterThan(0);
    });
    const folderButtons = screen
      .getByTestId('folderList')
      .querySelectorAll('button');
    expect(folderButtons.length).toBeGreaterThan(0);
    // Go into folderA to build up history
    fireEvent.click(folderButtons[0]);
    // Wait for historyPosition to update (back button enabled)
    await waitFor(() => {
      expect(screen.getByTestId('backButton')).not.toBeDisabled();
    });
    const backBtn = screen.getByTestId('backButton');
    const forwardBtn = screen.getByTestId('forwardButton');
    fireEvent.click(backBtn);
    await waitFor(() => {
      expect(forwardBtn).not.toBeDisabled();
    });
    fireEvent.click(forwardBtn);
  });

  it('navigates up with up button', async () => {
    render(<FolderSelector onSelect={vi.fn()} onClose={vi.fn()} />);
    // Wait for initial path to be set and up button to become enabled
    await screen.findByText('user');
    const upBtn = screen.getByTestId('upButton');
    fireEvent.click(upBtn);

    await waitFor(() => {
      const calls = (globalThis.fetch as any).mock.calls;
      expect(calls.length).toBeGreaterThan(1);
    });
    const calls = (globalThis.fetch as any).mock.calls;
    expect(calls[1][0]).toContain('path=%2Fhome');
  });

  it('toggles recents list', async () => {
    render(<FolderSelector onSelect={vi.fn()} onClose={vi.fn()} />);
    await screen.findByTestId('showRecentsButton');
    fireEvent.click(screen.getByTestId('showRecentsButton'));
    expect(screen.getByTestId('showRecentsButton').textContent).toMatch(
      /Show Recents/
    );
  });
});
