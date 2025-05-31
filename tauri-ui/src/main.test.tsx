import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

// @ts-ignore
vi.mock('./style.css', () => ({}), { virtual: true }); // mock CSS import
vi.mock('./components/App', () => ({
  App: () => <div data-testid="app-component">App Loaded</div>,
  __esModule: true,
}));
vi.mock('./context/ChatContext.tsx', async () => {
  const actual = await vi.importActual<typeof import('./context/ChatContext.tsx')>('./context/ChatContext.tsx');
  return {
    ...actual,
    ChatProvider: ({ children }: { children: any }) => <div data-testid="chat-provider">{children}</div>,
    __esModule: true,
  };
});

describe('main.tsx', () => {
  let root: HTMLDivElement;
  beforeEach(() => {
    root = document.createElement('div');
    root.id = 'app';
    document.body.appendChild(root);
    // Remove all children before each test
    while (root.firstChild) root.removeChild(root.firstChild);
    // Remove any cached module
    vi.resetModules();
  });

  afterEach(() => {
    root.remove();
  });

  it('renders App via ChatProvider into #app', async () => {
    // Import main.tsx after setting up DOM and mocks
    await import('./main.tsx');

    const provider = document.querySelector('[data-testid="chat-provider"]');
    expect(provider).toBeTruthy();

    const app = document.querySelector('[data-testid="app-component"]');
    expect(app).toBeTruthy();
    expect(app?.textContent).toContain('App Loaded');
    // Make sure it's rendered into #app node
    expect(root.contains(app!)).toBe(true);
  });
});
