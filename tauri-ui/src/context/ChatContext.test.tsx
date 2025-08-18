import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor } from '@testing-library/preact';
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

describe('ChatContext - extended', () => {
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
    vi.restoreAllMocks();
  });

  it('login and logout manage session and apiKey', async () => {
    let ctx: ReturnType<typeof useChat> | null = null;
    function Consumer() {
      ctx = useChat();
      return <div />;
    }
    render(
      <ChatProvider>
        <Consumer />
      </ChatProvider>
    );
    await waitFor(() => !!ctx);

    expect(ctx!.isAuthenticated).toBe(false);
    ctx!.login('u1', 'k1');
    await waitFor(() => ctx!.isAuthenticated === true);
    expect(ctx!.isAuthenticated).toBe(true);
    expect(ctx!.apiKey).toBe('k1');
    // setApiKey updates apiKey within session
    ctx!.setApiKey('k2');
    await waitFor(() => ctx!.apiKey === 'k2');
    expect(ctx!.apiKey).toBe('k2');
    // localStorage was set
    expect(localStorage.getItem('suhana_user_session')).toMatch(/"userId":"u1"/);

    ctx!.logout();
    await waitFor(() => ctx!.isAuthenticated === false);
    expect(ctx!.isAuthenticated).toBe(false);
    expect(localStorage.getItem('suhana_user_session')).toBeNull();
  });

  it('updateSettings posts and updates state', async () => {
    let ctx: ReturnType<typeof useChat> | null = null;
    function Consumer() {
      ctx = useChat();
      return <div />;
    }

    // Mock POST /settings/u1 response
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ settings: { llm_backend: 'ollama', llm_model: 'llama3', openai_model: 'gpt-4o-mini', voice: false, streaming: true, secured_streaming: false, openai_api_key: '' } })
    }) as any;

    render(
      <ChatProvider>
        <Consumer />
      </ChatProvider>
    );
    await waitFor(() => !!ctx);

    // login after mount to avoid provider auto-fetch
    ctx!.login('u1', 'k');
    await waitFor(() => ctx!.isAuthenticated === true);

    const updated = await ctx!.updateSettings({ llm_options: { ollama: ['llama3'], openai: ['gpt-4o-mini'] } as any });
    expect(updated.settings.llm_model).toBe('llama3');
    expect(updated.llm_options.openai[0]).toBe('gpt-4o-mini');
  });

  it('profile endpoints: getProfile and updateProfile', async () => {
    const profile = { name: 'Alice', created_at: '', last_login: null, role: 'user', avatar: null, preferences: {} as any, personalization: {} as any, privacy: {} as any, history: [] };

    // Order: first GET profile, then POST update
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ profile }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ profile: { ...profile, name: 'Alice B' } }) });

    let ctx: ReturnType<typeof useChat> | null = null;
    function Consumer() {
      ctx = useChat();
      return <div />;
    }
    render(
      <ChatProvider>
        <Consumer />
      </ChatProvider>
    );
    await waitFor(() => !!ctx);

    // authenticate after mount
    ctx!.login('u2', 'k');
    await waitFor(() => ctx!.isAuthenticated === true);

    const p1 = await ctx!.getProfile();
    expect(p1.profile.name).toBe('Alice');

    const p2 = await ctx!.updateProfile('u2', { name: 'Alice B' });
    expect(p2.profile.name).toBe('Alice B');
  });

  it('registerUser success and failure', async () => {
    // Success
    globalThis.fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ user_id: 'u3', api_key: 'k3' }) }) as any;
    let ctx: ReturnType<typeof useChat> | null = null;
    function Consumer() { ctx = useChat(); return <div />; }
    render(<ChatProvider><Consumer /></ChatProvider>);
    await waitFor(() => !!ctx);

    const r = await ctx!.registerUser('bob', 'pw', 'Bob');
    expect(r.user_id).toBe('u3');

    // Failure branch
    globalThis.fetch = vi.fn().mockResolvedValueOnce({ ok: false, text: async () => 'bad' }) as any;
    await expect(ctx!.registerUser('bob', 'pw')).rejects.toThrow(/bad|Registration failed/);
    // error state updated
    expect(ctx!.error).toMatch(/Registration failed/);
  });

  it('getFolders returns data', async () => {
    const payload = {
      current: '/home/user', parent: '/home', path_parts: [{ name: 'home', path: '/home' }], subfolders: [], separator: '/', recent_projects: []
    };
    globalThis.fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => payload }) as any;

    let ctx: ReturnType<typeof useChat> | null = null;
    function Consumer() { ctx = useChat(); return <div />; }
    render(<ChatProvider><Consumer /></ChatProvider>);
    await waitFor(() => !!ctx);

    const res = await ctx!.getFolders('/home/user');
    expect(res?.current).toBe('/home/user');
  });

  it('sendSecuredStreamingMessage delegates to consumeEncryptedStream', async () => {
    // Mock the module used inside ChatContext
    const tokens: string[] = [];
    const mod = await import('../utils/client-stream');
    const spy = vi.spyOn(mod, 'consumeEncryptedStream').mockResolvedValue(undefined as any).mockImplementation(async (_url, _key, _cid, onText) => {
      onText('hello-secure');
      return undefined as any;
    });

    let ctx: ReturnType<typeof useChat> | null = null;
    function Consumer() { ctx = useChat(); return <div />; }
    render(<ChatProvider><Consumer /></ChatProvider>);
    await waitFor(() => !!ctx);

    await ctx!.sendSecuredStreamingMessage('hi', t => tokens.push(t));
    expect(tokens).toEqual(['hello-secure']);
    expect(spy).toHaveBeenCalled();
  });
});
