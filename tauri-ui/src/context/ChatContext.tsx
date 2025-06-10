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

export interface Settings {
  llm_backend: string;
  llm_model: string;
  openai_model: string;
  voice: boolean;
  streaming: boolean;
  openai_api_key: string;
  [key: string]: any;
}

export interface UserProfile {
  name: string;
  created_at: string;
  last_login: string | null;
  role: string;
  avatar: string | null;
  preferences: UserPreferences;
  personalization: UserPersonalization;
  privacy: UserPrivacy;
  history: any[];
}

export interface UserPreferences {
  preferred_language: string;
  communication_style: string;
  focus: string;
  theme: string;
  font_size: string;
  notification_level: string;
  timezone: string;
  date_format: string;
  time_format: string;
}

export interface UserPersonalization {
  interests: string[];
  expertise: string[];
  learning_goals: string[];
  favorite_tools: string[];
  custom_shortcuts: Record<string, string>;
}

export interface UserPrivacy {
  share_conversations: boolean;
  allow_analytics: boolean;
  store_history: boolean;
}

export interface LLMOptions {
  ollama: string[];
  openai: string[];
}

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
  getSettings: () => Promise<{ settings: Settings; llm_options: LLMOptions }>;
  updateSettings: (
    settings: Partial<Settings>
  ) => Promise<{ settings: Settings }>;

  // User profile management
  currentUser: string | null;
  setCurrentUser: (userId: string | null) => void;
  getUsers: () => Promise<{ users: any[] }>;
  getProfile: (userId: string) => Promise<{ profile: UserProfile }>;
  updateProfile: (
    userId: string,
    profile: Partial<UserProfile>
  ) => Promise<{ profile: UserProfile }>;
  getPreferences: (userId: string) => Promise<{ preferences: UserPreferences }>;
  updatePreferences: (
    userId: string,
    preferences: Partial<UserPreferences>
  ) => Promise<{ preferences: UserPreferences }>;
  getPersonalization: (
    userId: string
  ) => Promise<{ personalization: UserPersonalization }>;
  updatePersonalization: (
    userId: string,
    personalization: Partial<UserPersonalization>
  ) => Promise<{ personalization: UserPersonalization }>;
  getPrivacySettings: (userId: string) => Promise<{ privacy: UserPrivacy }>;
  updatePrivacySettings: (
    userId: string,
    privacy: Partial<UserPrivacy>
  ) => Promise<{ privacy: UserPrivacy }>;

  // User registration
  registerUser: (
    username: string,
    password: string,
    name?: string
  ) => Promise<{ user_id: string; api_key: string }>;
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
  const [projectMetadata, setProjectMetadata] = useState<ProjectMeta | null>(
    null
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [apiKey, setApiKey] = useState(
    localStorage.getItem('suhana_key') || ''
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [currentUser, setCurrentUser] = useState<string | null>(
    localStorage.getItem('suhana_current_user') || null
  );
  const lastCheckedKey = useRef<string | null>(null);

  const apiReady = !error && !loading;
  useEffect(() => {
    if (!apiKey) {
      setLoading(false);
      return;
    }
    if (apiKey === lastCheckedKey.current) return;
    localStorage.setItem('suhana_key', apiKey);
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
    setMessages((data?.history as ChatMessage[]) || []);
    setProjectMetadata((data?.project_metadata as ProjectMeta) || null);
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
    return (data?.text as string) || '';
  };

  const getSettings = async () => {
    const data = await fetchWithKey(`${BASE_URL}/settings`, apiKey, setError);
    return {
      settings: data?.settings as Settings,
      llm_options: data?.llm_options as LLMOptions
    };
  };

  const updateSettings = async (settings: Partial<Settings>) => {
    const data = await fetchWithKey(`${BASE_URL}/settings`, apiKey, setError, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(settings)
    });
    return { settings: data?.settings as Settings };
  };

  // User profile management methods
  const getUsers = async () => {
    const data = await fetchWithKey(`${BASE_URL}/users`, apiKey, setError);
    return { users: data?.users || [] };
  };

  const getProfile = async (userId: string) => {
    const data = await fetchWithKey(
      `${BASE_URL}/profile/${userId}`,
      apiKey,
      setError
    );
    return { profile: data?.profile as UserProfile };
  };

  const updateProfile = async (
    userId: string,
    profile: Partial<UserProfile>
  ) => {
    const data = await fetchWithKey(
      `${BASE_URL}/profile/${userId}`,
      apiKey,
      setError,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(profile)
      }
    );
    return { profile: data?.profile as UserProfile };
  };

  const getPreferences = async (userId: string) => {
    const data = await fetchWithKey(
      `${BASE_URL}/profile/${userId}/preferences`,
      apiKey,
      setError
    );
    return { preferences: data?.preferences as UserPreferences };
  };

  const updatePreferences = async (
    userId: string,
    preferences: Partial<UserPreferences>
  ) => {
    const data = await fetchWithKey(
      `${BASE_URL}/profile/${userId}/preferences`,
      apiKey,
      setError,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(preferences)
      }
    );
    return { preferences: data?.preferences as UserPreferences };
  };

  const getPersonalization = async (userId: string) => {
    const data = await fetchWithKey(
      `${BASE_URL}/profile/${userId}/personalization`,
      apiKey,
      setError
    );
    return { personalization: data?.personalization as UserPersonalization };
  };

  const updatePersonalization = async (
    userId: string,
    personalization: Partial<UserPersonalization>
  ) => {
    const data = await fetchWithKey(
      `${BASE_URL}/profile/${userId}/personalization`,
      apiKey,
      setError,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(personalization)
      }
    );
    return { personalization: data?.personalization as UserPersonalization };
  };

  const getPrivacySettings = async (userId: string) => {
    const data = await fetchWithKey(
      `${BASE_URL}/profile/${userId}/privacy`,
      apiKey,
      setError
    );
    return { privacy: data?.privacy as UserPrivacy };
  };

  const updatePrivacySettings = async (
    userId: string,
    privacy: Partial<UserPrivacy>
  ) => {
    const data = await fetchWithKey(
      `${BASE_URL}/profile/${userId}/privacy`,
      apiKey,
      setError,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(privacy)
      }
    );
    return { privacy: data?.privacy as UserPrivacy };
  };

  const registerUser = async (
    username: string,
    password: string,
    name?: string
  ) => {
    try {
      const response = await fetch(`${BASE_URL}/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          username,
          password,
          name: name || username
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Registration failed');
      }

      const data = await response.json();
      return {
        user_id: data.user_id,
        api_key: data.api_key
      };
    } catch (err) {
      setError(`Registration failed: ${(err as Error).message}`);
      throw err;
    }
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
        setProjectMetadata,
        getSettings,
        updateSettings,

        // User profile management
        currentUser,
        setCurrentUser: (userId: string | null) => {
          setCurrentUser(userId);
          if (userId) {
            localStorage.setItem('suhana_current_user', userId);
          } else {
            localStorage.removeItem('suhana_current_user');
          }
        },
        getUsers,
        getProfile,
        updateProfile,
        getPreferences,
        updatePreferences,
        getPersonalization,
        updatePersonalization,
        getPrivacySettings,
        updatePrivacySettings,
        registerUser
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
