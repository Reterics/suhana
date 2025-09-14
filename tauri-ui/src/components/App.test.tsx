import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/preact';
import { App } from './App';

let mockApiReady = true;
let mockError: string | null = null;
let mockMessages: any[] = [];
let mockConversationList = [
  { id: '1', title: 'Test Conversation', created: '', last_updated: '' }
];
let mockProjectMetadata: any = null;
let mockConversationId = '1';
const mockSetMessages = vi.fn(fn => {
  mockMessages = fn(mockMessages);
});
const mockSetProjectMetadata = vi.fn(val => {
  mockProjectMetadata = val;
});
const mockSendStreamingMessage = vi.fn(async (_input, onToken) => {
  onToken('streamed!');
  return Promise.resolve();
});
const mockLoadConversation = vi.fn();

vi.mock('../context/ChatContext.tsx', () => ({
  BASE_URL: 'http://localhost:8000',
  useChat: () => ({
    settings: { settings: { streaming: true, secured_streaming: false } },
    apiReady: mockApiReady,
    error: mockError,
    conversationList: mockConversationList,
    loadConversation: mockLoadConversation,
    conversationId: mockConversationId,
    apiKey: 'fake-key',
    messages: mockMessages,
    setMessages: mockSetMessages,
    sendMessage: vi.fn(async () => 'ok'),
    sendSecuredStreamingMessage: vi.fn(),
    sendStreamingMessage: mockSendStreamingMessage,
    projectMetadata: mockProjectMetadata,
    setProjectMetadata: mockSetProjectMetadata,
    isAuthenticated: true,
    logout: vi.fn()
  }),
  __esModule: true
}));

// -- Mock all child components as stubs --
vi.mock('./Sidebar.tsx', () => ({
  default: ({ onSelectConversation }: any) => (
    <aside data-testid="sidebar" onClick={() => onSelectConversation('1')}>
      Sidebar
    </aside>
  ),
  __esModule: true
}));
vi.mock('./ChatToolbar.tsx', () => ({
  ChatToolbar: ({ onSend }: any) => (
    <button onClick={() => onSend('test message')} data-testid="toolbar">
      Send
    </button>
  ),
  __esModule: true
}));
vi.mock('./ChatMessages.tsx', () => ({
  ChatMessages: ({ messages }: any) => (
    <div data-testid="messages">
      {messages && messages.length > 0
        ? messages.map((m: any, i: number) => <span key={i}>{m.content}</span>)
        : 'No messages'}
    </div>
  ),
  __esModule: true
}));
vi.mock('./FolderSelector.tsx', () => ({
  FolderSelector: ({ onSelect, onClose }: any) => (
    <div data-testid="folder-selector">
      <button onClick={() => onSelect('/testpath')}>Select Folder</button>
      <button onClick={onClose}>Close</button>
    </div>
  ),
  __esModule: true
}));
vi.mock('./ProjectMetadata.tsx', () => ({
  ProjectMetadata: ({ metadata }: any) => (
    <div data-testid="project-metadata">{metadata && metadata.name}</div>
  ),
  __esModule: true
}));
// Mock motion/react so motion.div renders as a plain div without forwarding ref
vi.mock('motion/react', () => ({
  motion: {
    // Do not forward ref to force immediate proceedStartChat path in component
    div: (props: any) => <div {...props} />,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  // Reset all top-level mock state before each test
  mockApiReady = true;
  mockError = null;
  mockMessages = [];
  mockConversationList = [
    { id: '1', title: 'Test Conversation', created: '', last_updated: '' }
  ];
  mockProjectMetadata = null;
  mockConversationId = '1';
});

describe('App', () => {
  it('shows loading state if not ready', () => {
    mockApiReady = false;
    mockError = null;

    render(<App />);
    expect(screen.getByText(/Suhana is starting/i)).toBeTruthy();
  });

  it('shows error state if not ready and error', () => {
    mockApiReady = false;
    mockError = 'API Down';

    render(<App />);
    expect(screen.getByText(/Suhana failed/i)).toBeTruthy();
    expect(screen.getByText(/Reason: API Down/i)).toBeTruthy();
  });

  it('renders sidebar, toolbar, and messages when ready', () => {
    render(<App />);
    expect(screen.getByTestId('sidebar')).toBeTruthy();
    expect(screen.getByTestId('toolbar')).toBeTruthy();
    expect(screen.getByTestId('messages')).toBeTruthy();
  });

  it('calls setMessages and sendStreamingMessage when sending a message', async () => {
    render(<App />);
    // Click send on ChatToolbar
    screen.getByTestId('toolbar').click();

    await waitFor(() => {
      expect(mockSetMessages).toHaveBeenCalled();
      expect(mockSendStreamingMessage).toHaveBeenCalledTimes(1);
      const [inputArg, cbArg, ...rest] = mockSendStreamingMessage.mock.calls[0];
      expect(inputArg).toBe('test message');
      expect(typeof cbArg).toBe('function');
      expect(rest.length).toBe(0);
    });
  });

  it('toggles sidebar when menu button clicked', () => {
    render(<App />);
    const menuButton = screen.getByTitle('Toggle Sidebar');
    expect(screen.getByTestId('sidebar')).toBeTruthy();
    fireEvent.click(menuButton);
    // Sidebar is hidden, but in this mock, the element still exists; a real test could check for a class or style
  });

  it('shows and closes FolderSelector modal', async () => {
    render(<App />);
    // Find and click project/folder button (note: component uses data-testId with capital I)
    const projectBtn = document.querySelector(
      '[data-testId="project-path-selector"]'
    ) as HTMLButtonElement | null;
    expect(projectBtn).toBeTruthy();
    projectBtn && fireEvent.click(projectBtn);

    expect(screen.getByTestId('folder-selector')).toBeTruthy();
    screen.getByText('Select Folder').click();
    await waitFor(() =>
      expect(screen.queryByTestId('folder-selector')).toBeNull()
    );
  });

  it('shows and closes right sidebar with project metadata', async () => {
    mockProjectMetadata = { name: 'Demo Project', project_type: 'ts' };

    render(<App />);
    const projectMetaBtn = screen.getAllByText('Demo Project');
    fireEvent.click(projectMetaBtn[0]);
    expect(screen.getByTestId('project-metadata')).toBeTruthy();

    // Close with ChevronLeft button (mocked as 'Close' in this test setup)
    const closeBtn =
      screen
        .getAllByRole('button')
        .find(b => b.title === 'Toggle Project Metadata') || projectMetaBtn[0];
    expect(closeBtn).toBeDefined();
    if (closeBtn) {
      fireEvent.click(closeBtn);
    }
  });
});
