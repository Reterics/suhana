import { createContext } from 'preact';
import {
  StateUpdater,
  useContext,
  useEffect,
  useRef,
  useState
} from 'preact/hooks';
import { Dispatch } from 'preact/compat';

export type ChatMessage = {
  role: 'user' | 'assistant' | 'system';
  content: string;
};

interface ChatState {
  conversationId: string;
  messages: ChatMessage[];
  apiKey: string;
  apiReady: boolean;
  error: string | null;
  setApiKey: (key: string) => void;
  setMessages: Dispatch<StateUpdater<ChatMessage[]>>;
  sendMessage: (input: string, backend?: string) => Promise<string>;
  sendStreamingMessage: (
    input: string,
    onToken: (token: string) => void,
    backend?: string
  ) => Promise<void>;
  conversationList: ConversationMeta[];
  loadConversation: (id: string) => Promise<void>;
  transcribe: (blob: Blob) => Promise<string>;
  projectMetadata: ProjectMeta | null;
  setProjectMetadata: Dispatch<StateUpdater<ProjectMeta | null>>;
}

export interface ConversationMeta {
  id: string;
  title: string;
  created: string;
  last_updated: string;
}

export interface ProjectMeta extends Record<string, unknown> {
  name?: string;
  project_type: string;
  dependencies?: string[];
}

const ChatContext = createContext<ChatState | null>(null);

export const BASE_URL = 'http://localhost:8000';

async function fetchWithKey(
  url: string,
  apiKey: string,
  setError: (val: string | null) => void,
  options: RequestInit = {},
  maxRetries = 3,
  retryDelayMs = 1000
): Promise<Record<string, unknown> | null | undefined> {
  const isGet = (options.method || 'GET').toUpperCase() === 'GET';
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(url, {
        ...options,
        headers: {
          ...(options.headers || {}),
          ...(apiKey ? { 'x-api-key': apiKey } : {})
        }
      });
      if (!res?.ok) {
        const text = await res.text().catch(() => res.statusText);
        throw new Error(text || 'Fetch failed');
      }
      setError(null);
      return res.json();
    } catch (err: unknown) {
      if (!isGet || attempt === maxRetries) {
        setError(
          `${(err as Error).message || 'Fetch failed'} URL: ${url.replace(BASE_URL, '')}`
        );
        return null;
      }
      await new Promise(resolve => setTimeout(resolve, retryDelayMs));
    }
  }
}

export function ChatProvider({
  children
}: {
  children: preact.ComponentChildren;
}) {
  const [conversationId, setConversationId] = useState('');
  const [conversationList, setConversationList] = useState<ConversationMeta[]>(
    []
  );
  const [projectMetadata, setProjectMetadata] = useState<ProjectMeta|null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [apiKey, setApiKey] = useState(
    localStorage.getItem('suhana_key') || ''
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const lastCheckedKey = useRef<string | null>(null);

  const apiReady = !error && !loading;
  useEffect(() => {
    if (!apiKey) {
      setLoading(false);
      return;
    }
    if (apiKey === lastCheckedKey.current) return;
    localStorage.setItem('suhana_key', apiKey)
    lastCheckedKey.current = apiKey;
    void listConversations().then(() => setLoading(false));
  }, [apiKey]);

  const listConversations = async () => {
    const conversations = await fetchWithKey(
      `${BASE_URL}/conversations`,
      apiKey,
      setError
    );
    if (Array.isArray(conversations)) {
      setConversationList(conversations);
    }
  };

  const loadConversation = async (id: string) => {
    const data = await fetchWithKey(
      `${BASE_URL}/conversations/${id}`,
      apiKey,
      setError
    );
    setConversationId(id);
    setMessages(data?.history as ChatMessage[] || []);
    setProjectMetadata(data?.project_metadata as ProjectMeta || null)
  };

  const sendMessage = async (
    input: string,
    backend = 'ollama',
    mode?: string,
    project_path?: string
  ) => {
    const data = await fetchWithKey(`${BASE_URL}/query`, apiKey, setError, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        input,
        backend,
        conversation_id: conversationId,
        mode,
        project_path
      })
    });
    return data?.response as string;
  };

  const sendStreamingMessage = async (
    input: string,
    onToken: (token: string) => void,
    backend = 'ollama',
    mode?: string,
    project_path?: string
  ) => {
    const res = await fetch(`${BASE_URL}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? { 'x-api-key': apiKey } : {})
      },
      body: JSON.stringify({
        input,
        backend,
        conversation_id: conversationId,
        mode,
        project_path
      })
    });
    const reader = res.body?.getReader();
    const decoder = new TextDecoder('utf-8');
    while (reader) {
      const { value, done } = await reader.read();
      if (done) break;
      if (value) onToken(decoder.decode(value));
    }
  };

  const transcribe = async (blob: Blob): Promise<string> => {
    const form = new FormData();
    form.append('audio', blob, 'speech.webm');
    const data = await fetchWithKey(
      `${BASE_URL}/transcribe`,
      apiKey,
      setError,
      {
        method: 'POST',
        headers: apiKey ? { 'x-api-key': apiKey } : {},
        body: form
      }
    );
    return data?.text as string || '';
  };

  return (
    <ChatContext.Provider
      value={{
        conversationId,
        messages,
        setMessages,
        apiKey,
        setApiKey: (key: string) => {
          setApiKey(key);
          localStorage.setItem('suhana_key', key);
        },
        apiReady,
        error,
        conversationList,
        loadConversation,
        sendMessage,
        sendStreamingMessage,
        transcribe,
        projectMetadata,
        setProjectMetadata
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export const useChat = () => {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChat must be used within a <ChatProvider>');
  return ctx;
};
