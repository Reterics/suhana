import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/preact';
import { ChatProvider, useChat, BASE_URL } from './ChatContext';
import type { ChatMessage, ProjectMeta } from './ChatContext';

const mockProjectMeta: ProjectMeta = {
  name: 'Demo Project',
  project_type: 'ts'
};
const mockHistory: ChatMessage[] = [
  { role: 'user', content: 'hi' },
  { role: 'assistant', content: 'hello' }
];

describe('ChatContext', () => {
  let originalFetch: typeof fetch;
  let localStorageMock: Storage;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    localStorageMock = (() => {
      let store: Record<string, string> = {};
      return {
        getItem: (k: string) => store[k] || null,
        setItem: (k: string, v: string) => {
          store[k] = v;
        },
        removeItem: (k: string) => {
          delete store[k];
        },
        clear: () => {
          store = {};
        }
      } as Storage;
    })();
    globalThis.localStorage = localStorageMock;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.resetAllMocks();
  });

  it('throws if useChat used outside provider', () => {
    function UseChatConsumer() {
      useChat();
      return null;
    }
    expect(() => render(<UseChatConsumer />)).toThrow(
      /useChat must be used within a <ChatProvider>/
    );
  });

  it('provides initial context and can set API key', async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => []
    }) as any;

    function Consumer() {
      const chat = useChat();
      return (
        <div>
          <button onClick={() => chat.setApiKey('abc')}>SetKey</button>
          <div data-testid="apiKey">{chat.apiKey}</div>
        </div>
      );
    }

    render(
      <ChatProvider>
        <Consumer />
      </ChatProvider>
    );
    // initial: ''
    expect(screen.getByTestId('apiKey').textContent).toBe('');

    // set an API key and it should update
    screen.getByText('SetKey').click();
    await waitFor(() =>
      expect(screen.getByTestId('apiKey').textContent).toBe('abc')
    );
    // should persist to localStorage
    expect(localStorageMock.getItem('suhana_key')).toBe('abc');
  });

  it('can load conversation and set messages/projectMetadata', async () => {
    // mock fetch for loadConversation
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        history: mockHistory,
        project_metadata: mockProjectMeta
      })
    }) as any;

    let testChat: ReturnType<typeof useChat> | null = null;
    function Consumer() {
      testChat = useChat();
      return <div />;
    }
    render(
      <ChatProvider>
        <Consumer />
      </ChatProvider>
    );
    // Wait for provider to finish first fetch
    await waitFor(() => !!testChat);

    // loadConversation
    await testChat!.loadConversation('1');
    expect(testChat!.messages).toEqual(mockHistory);
    expect(testChat!.projectMetadata).toEqual(mockProjectMeta);
  });

  it('sendMessage posts and returns response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ response: 'pong' })
    }) as any;

    let testChat: ReturnType<typeof useChat> | null = null;
    function Consumer() {
      testChat = useChat();
      return <div />;
    }
    render(
      <ChatProvider>
        <Consumer />
      </ChatProvider>
    );
    await waitFor(() => !!testChat);

    const resp = await testChat!.sendMessage('ping');
    expect(resp).toBe('pong');

    // Test fetch args
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${BASE_URL}/query`,
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json'
        }),
        body: expect.stringContaining('ping')
      })
    );
  });

  it('sendStreamingMessage yields tokens', async () => {
    // Mock fetch and streaming response
    const readChunks = [
      { value: new TextEncoder().encode('hi'), done: false },
      { value: undefined, done: true }
    ];
    const getReader = () => ({
      read: vi
        .fn()
        .mockResolvedValueOnce(readChunks[0])
        .mockResolvedValueOnce(readChunks[1])
    });

    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      body: { getReader }
    }) as any;

    const tokens: string[] = [];
    let testChat: ReturnType<typeof useChat> | null = null;
    function Consumer() {
      testChat = useChat();
      return <div />;
    }
    render(
      <ChatProvider>
        <Consumer />
      </ChatProvider>
    );
    await waitFor(() => !!testChat);

    await testChat!.sendStreamingMessage('foo', t => tokens.push(t));
    expect(tokens).toContain('hi');
  });

  it('transcribe calls /transcribe and returns text', async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ text: 'hello world' })
    }) as any;

    let testChat: ReturnType<typeof useChat> | null = null;
    function Consumer() {
      testChat = useChat();
      return <div />;
    }
    render(
      <ChatProvider>
        <Consumer />
      </ChatProvider>
    );
    await waitFor(() => !!testChat);

    // Dummy blob
    const blob = new Blob(['test'], { type: 'audio/webm' });
    const result = await testChat!.transcribe(blob);
    expect(result).toBe('hello world');
  });

  it('sets error if fetch fails', async () => {
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      text: async () => 'fail',
      statusText: 'fail'
    }) as any;

    let testChat: ReturnType<typeof useChat> | null = null;
    function Consumer() {
      testChat = useChat();
      return <div />;
    }
    render(
      <ChatProvider>
        <Consumer />
      </ChatProvider>
    );
    await waitFor(() => !!testChat);

    // trigger a fetch
    const result = await testChat!.sendMessage('will fail');
    expect(result).toBeUndefined();
    expect(testChat!.error).toMatch(/fail/);
  });
});
