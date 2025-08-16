import { createContext } from 'preact';
import {
  StateUpdater,
  useContext,
  useEffect,
  useState
} from 'preact/hooks';
import { Dispatch } from 'preact/compat';
import { v4 } from 'uuid';
import {consumeEncryptedStream} from "../utils/client-stream.ts";
import {FolderInfo, PathPart} from "../components/FolderSelector.tsx";

export type ChatMessage = {
  role: 'user' | 'assistant' | 'system';
  content: string;
};

export type SettingsType = {
  llm_backend: string;
  llm_model: string;
  openai_model: string;
  voice: boolean;
  streaming: boolean;
  secured_streaming: boolean;
  openai_api_key: string;
}

export type AppSettings = {
  settings: SettingsType
  llm_options: LLMOptions
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

export interface UserSession {
  userId: string;
  apiKey: string;
  lastLogin: Date;
}

interface BrowseFoldersResponse {
  current: string;
  parent: string | null;
  path_parts: PathPart[];
  subfolders: FolderInfo[];
  separator: string;
  recent_projects: string[];
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
  sendSecuredStreamingMessage: (
    input: string,
    onToken: (token: string) => void,
    backend?: string
  ) => Promise<void>;
  conversationList: ConversationMeta[];
  loadConversation: (id: string) => Promise<void>;
  addConversation: () => Promise<void>;
  transcribe: (blob: Blob) => Promise<string>;
  projectMetadata: ProjectMeta | null;
  setProjectMetadata: Dispatch<StateUpdater<ProjectMeta | null>>;
  settings: AppSettings | null;
  updateSettings: (
    settings: Partial<AppSettings>
  ) => Promise<AppSettings>;

  // User session management
  userSession: UserSession | null;
  login: (userId: string, apiKey: string) => void;
  logout: () => void;
  isAuthenticated: boolean;

  // User profile management
  getUsers: () => Promise<{ users: any[] }>;
  getProfile: (userId?: string) => Promise<{ profile: UserProfile }>;
  updateProfile: (
    userId: string,
    profile: Partial<UserProfile>
  ) => Promise<{ profile: UserProfile }>;
  getPreferences: (userId?: string) => Promise<{ preferences: UserPreferences }>;
  updatePreferences: (
    userId: string,
    preferences: Partial<UserPreferences>
  ) => Promise<{ preferences: UserPreferences }>;
  getPersonalization: (
    userId?: string
  ) => Promise<{ personalization: UserPersonalization }>;
  updatePersonalization: (
    userId: string,
    personalization: Partial<UserPersonalization>
  ) => Promise<{ personalization: UserPersonalization }>;
  getPrivacySettings: (userId?: string) => Promise<{ privacy: UserPrivacy }>;
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

  getFolders: (path: string) => Promise<BrowseFoldersResponse | null>
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
  const isGet = (options.method || 'GET').toUpperCase() === 'GET' || options.method === undefined;
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
  const [error, setError] = useState<string | null>(null);
  const [userSession, setUserSession] = useState<UserSession | null>(() => {
    const storedSession = localStorage.getItem('suhana_user_session');
    if (storedSession) {
      try {
        return JSON.parse(storedSession);
      } catch (e) {
        console.error('Failed to parse user session from localStorage', e);
        return null;
      }
    }
    return null;
  });
  const [loading, setLoading] = useState<boolean>(!!userSession);
  const apiKey = userSession?.apiKey || '';
  const setApiKey = (key: string) => {
    setUserSession((prev) =>
      prev ? ({...prev, apiKey: key}) : null);
  }

  const [settings, setSettings] = useState<AppSettings | null>(null);

  const apiReady = !error && !loading;

  const isAuthenticated = !!userSession?.userId && !!userSession?.apiKey;

  const onLoad = async () => {
    await listConversations();
    const settings = await getSettings();
    setSettings(settings);
  };

  useEffect(() => {
    if (userSession && loading) {
      onLoad().then(() => setLoading(false));
      void listConversations();
    } else if (!userSession && !loading) {
      setLoading(false);
    }
  }, [userSession, loading])

  const listConversations = async () => {
    const conversations = await fetchWithKey(
      `${BASE_URL}/conversations`,
      apiKey,
      setError,
      undefined,
      10
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

  const addConversation = async () => {
    setConversationId(v4());
    setMessages([]);
    setProjectMetadata(null);
  }

  const addTemporaryConversation = (input: string) => {
    const isoNow = new Date().toISOString().substring(0, 23);
    setConversationList([
      ...conversationList,
      {
        title: input.substring(0, 15) + (input.length > 15 ? '...' : ''),
        last_updated: isoNow,
        created: isoNow,
        id: conversationId
      }
    ])
  }

  const sendMessage = async (
    input: string,
    backend = 'ollama',
    mode?: string,
    project_path?: string
  ) => {
    const data = await fetchWithKey(`${BASE_URL}/query`, apiKey, setError, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        input,
        backend,
        conversation_id: conversationId,
        mode,
        project_path
      })
    });
    if (messages.length === 0) {
      addTemporaryConversation(input)
    }
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
    if (messages.length === 0) {
      addTemporaryConversation(input)
    }
    while (reader) {
      const { value, done } = await reader.read();
      if (done) break;
      if (value) onToken(decoder.decode(value));
    }
  };

  const sendSecuredStreamingMessage = (
    input: string,
    onToken: (token: string) => void,
    backend = 'ollama',
    mode?: string,
    project_path?: string
  )=> {
    if (messages.length === 0) {
      addTemporaryConversation(input)
    }
    return consumeEncryptedStream(
      `${BASE_URL}/query/secure_stream`,
      apiKey,
      conversationId,
      onToken,
      JSON.stringify({
        input,
        backend,
        conversation_id: conversationId,
        mode,
        project_path
      })
    )
  }

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
    if (!userSession?.userId) {
      throw new Error('User must be authenticated to load settings');
    }
    const data = await fetchWithKey(`${BASE_URL}/settings/${userSession.userId}`, apiKey, setError);
    return data as AppSettings;
  };

  const updateSettings = async (settings: Partial<AppSettings>) => {
    if (!userSession?.userId) {
      throw new Error('User must be authenticated to update settings');
    }
    const url = `${BASE_URL}/settings/${userSession.userId}`;
    const data = await fetchWithKey(url, apiKey, setError, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(settings)
    }) as { settings: SettingsType } | null | undefined;
    let updatedSettings = settings as AppSettings;
    if (data) {
      updatedSettings = {
        settings: {...data.settings},
        llm_options: settings.llm_options as LLMOptions
      };
      setSettings(updatedSettings);
    }

    return updatedSettings;
  };

  // User profile management methods
  const getUsers = async () => {
    const data = await fetchWithKey(`${BASE_URL}/users`, apiKey, (e) => console.error(e)) as {users: UserProfile[]};
    return { users: data?.users || [] };
  };

  const getProfile = async (userId?: string) => {
    const targetUserId = userId || userSession?.userId;
    if (!targetUserId) {
      throw new Error('User ID is required when not authenticated');
    }

    const data = await fetchWithKey(
      `${BASE_URL}/profile/${targetUserId}`,
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

  const getPreferences = async (userId?: string) => {
    const targetUserId = userId || userSession?.userId;
    if (!targetUserId) {
      throw new Error('User ID is required when not authenticated');
    }

    const data = await fetchWithKey(
      `${BASE_URL}/profile/${targetUserId}/preferences`,
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

  const getPersonalization = async (userId?: string) => {
    const targetUserId = userId || userSession?.userId;
    if (!targetUserId) {
      throw new Error('User ID is required when not authenticated');
    }

    const data = await fetchWithKey(
      `${BASE_URL}/profile/${targetUserId}/personalization`,
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

  const getPrivacySettings = async (userId?: string) => {
    const targetUserId = userId || userSession?.userId;
    if (!targetUserId) {
      throw new Error('User ID is required when not authenticated');
    }

    const data = await fetchWithKey(
      `${BASE_URL}/profile/${targetUserId}/privacy`,
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

  // Login method to create a user session
  const login = (userId: string, apiKey: string) => {
    const session: UserSession = {
      userId,
      apiKey,
      lastLogin: new Date()
    };
    setUserSession(session);
    localStorage.setItem('suhana_user_session', JSON.stringify(session));
  };

  // Logout method to clear the user session
  const logout = () => {
    setUserSession(null);
    localStorage.removeItem('suhana_user_session');
    localStorage.removeItem('suhana_key');
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

  const getFolders = async (path: string): Promise<BrowseFoldersResponse | null> => {
     const folders = await fetchWithKey(
       `${BASE_URL}/browse-folders?path=${encodeURIComponent(path)}`,
       apiKey,
       (e) => {
         if (e) {
           throw new Error(e || 'Failed to fetch folders');
         }
       },
       undefined,
       1
     ) as unknown as Promise<BrowseFoldersResponse | null>;

     console.error('Returned folders', folders)
     return folders;
  }

  return (
    <ChatContext.Provider
      value={{
        conversationId,
        messages,
        setMessages,
        apiKey,
        setApiKey,
        apiReady,
        error,
        conversationList,
        loadConversation,
        addConversation,
        sendMessage,
        sendStreamingMessage,
        sendSecuredStreamingMessage,
        transcribe,
        projectMetadata,
        setProjectMetadata,

        settings,
        updateSettings,

        // User session management
        userSession,
        login,
        logout,
        isAuthenticated,

        // User profile management
        getUsers,
        getProfile,
        updateProfile,
        getPreferences,
        updatePreferences,
        getPersonalization,
        updatePersonalization,
        getPrivacySettings,
        updatePrivacySettings,
        registerUser,
        getFolders
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
