import { useEffect, useState } from 'preact/hooks';
import {
  Settings as SettingsType,
  LLMOptions,
  UserProfile,
  UserPreferences,
  UserPersonalization,
  UserPrivacy,
  useChat
} from '../context/ChatContext';
import { Settings as SettingsIcon, User, X } from 'lucide-preact';

interface SettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Settings({ isOpen, onClose }: SettingsProps) {
  const {
    getSettings,
    updateSettings,
    userSession,
    login,
    getUsers,
    getProfile,
    updateProfile,
    getPreferences,
    updatePreferences,
    getPersonalization,
    updatePersonalization,
    getPrivacySettings,
    updatePrivacySettings
  } = useChat();

  // Settings state
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [llmOptions, setLlmOptions] = useState<LLMOptions | null>(null);

  // Profile state
  const [users, setUsers] = useState<any[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [personalization, setPersonalization] =
    useState<UserPersonalization | null>(null);
  const [privacy, setPrivacy] = useState<UserPrivacy | null>(null);

  // UI state
  const [activeTab, setActiveTab] = useState<
    'settings' | 'profile' | 'register'
  >('settings');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Registration state
  const [registrationForm, setRegistrationForm] = useState({
    username: '',
    password: '',
    confirmPassword: '',
    name: ''
  });
  const [registrationSuccess, setRegistrationSuccess] = useState<{
    user_id: string;
    api_key: string;
  } | null>(null);

  useEffect(() => {
    if (isOpen) {
      void loadSettings();
      void loadUsers();
      if (userSession?.userId) {
        void loadProfileData(userSession.userId);
      }
    }
  }, [isOpen, userSession]);

  async function loadSettings() {
    setLoading(true);
    try {
      const { settings, llm_options } = await getSettings();
      setSettings(settings);
      setLlmOptions(llm_options);
      setError(null);
    } catch (err) {
      setError('Failed to load settings');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function loadUsers() {
    try {
      const { users: usersList } = await getUsers();
      setUsers(usersList);

      // If no current user is selected and users exist, select the first one
      if (!userSession?.userId && usersList.length > 0) {
        // Create a new session with the first user
        login(usersList[0].user_id, userSession?.apiKey || '');
      }
    } catch (err) {
      console.error('Failed to load users', err);
    }
  }

  async function loadProfileData(userId: string) {
    try {
      // Load profile data in parallel
      const [profileData, preferencesData, personalizationData, privacyData] =
        await Promise.all([
          getProfile(userId),
          getPreferences(userId),
          getPersonalization(userId),
          getPrivacySettings(userId)
        ]);

      setProfile(profileData.profile);
      setPreferences(preferencesData.preferences);
      setPersonalization(personalizationData.personalization);
      setPrivacy(privacyData.privacy);
    } catch (err) {
      console.error(`Failed to load profile data for user ${userId}`, err);
    }
  }

  async function handleSave() {
    setSaving(true);
    try {
      if (activeTab === 'settings' && settings) {
        const result = await updateSettings(settings);
        setSettings(result.settings);
        setError(null);
      } else if (activeTab === 'profile' && userSession?.userId && profile) {
        const userId = userSession.userId;

        // Save profile changes
        await updateProfile(userId, { name: profile.name });

        // Save preferences if changed
        if (preferences) {
          await updatePreferences(userId, preferences);
        }

        // Save personalization if changed
        if (personalization) {
          await updatePersonalization(userId, personalization);
        }

        // Save privacy settings if changed
        if (privacy) {
          await updatePrivacySettings(userId, privacy);
        }

        setError(null);
      }
    } catch (err) {
      setError(
        `Failed to save ${activeTab === 'settings' ? 'settings' : 'profile'}`
      );
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  function handleChange(key: keyof SettingsType, value: any) {
    if (!settings) return;
    setSettings({ ...settings, [key]: value });
  }

  if (!isOpen) return null;
  console.error(userSession?.userId, profile, preferences, personalization, privacy);
  return (
    <div
      className="fixed inset-0 bg-black/40 z-40 flex items-center justify-center"
      onClick={onClose}
    >
      <div
        className="w-[90%] max-w-xl relative z-50 bg-white border border-gray-200 rounded-md shadow-md p-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between pb-2 border-b border-gray-100 mb-2">
          <h3 className="font-semibold text-lg text-gray-800 flex items-center gap-2">
            {activeTab === 'settings' ? (
              <SettingsIcon className="w-5 h-5" />
            ) : (
              <User className="w-5 h-5" />
            )}
            {activeTab === 'settings' ? 'Settings' : 'Profile'}{' '}
            {loading && (
              <span className="text-sm text-gray-400">Loading...</span>
            )}
          </h3>
          <button
            onClick={onClose}
            className="cursor-pointer text-gray-400 hover:text-black hover:bg-gray-100 rounded-md p-2 focus:outline-none transition"
            title="Close"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex border-b border-gray-200 mb-4">
          <button
            onClick={() => setActiveTab('settings')}
            className={`px-4 py-2 font-medium text-sm ${
              activeTab === 'settings'
                ? 'text-black border-b-2 border-black'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            General Settings
          </button>
          <button
            onClick={() => setActiveTab('profile')}
            className={`px-4 py-2 font-medium text-sm ${
              activeTab === 'profile'
                ? 'text-black border-b-2 border-black'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            User Profile
          </button>
          <button
            onClick={() => setActiveTab('register')}
            className={`px-4 py-2 font-medium text-sm ${
              activeTab === 'register'
                ? 'text-black border-b-2 border-black'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Register User
          </button>
        </div>

        {error && (
          <div className="bg-red-50 text-red-700 p-3 rounded border border-red-200 text-sm mb-4">
            {error}
          </div>
        )}

        {!loading && (
          <div className="max-h-[60vh] overflow-y-auto pr-1">
            {activeTab === 'settings' && settings && llmOptions && (
              <form
                data-testid="settings-form"
                onSubmit={e => {
                  e.preventDefault();
                  void handleSave();
                }}
                className="flex flex-col gap-4"
              >
                <div>
                  <label
                    htmlFor="llm-backend"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    LLM Backend
                  </label>
                  <select
                    id="llm-backend"
                    value={settings.llm_backend}
                    onChange={e =>
                      handleChange('llm_backend', e.currentTarget.value)
                    }
                    className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-black"
                  >
                    <option value="ollama">Ollama</option>
                    <option value="openai">OpenAI</option>
                  </select>
                </div>

                {settings.llm_backend === 'ollama' ? (
                  <div>
                    <label
                      htmlFor="ollama-model"
                      className="block text-sm font-medium text-gray-700 mb-1"
                    >
                      Ollama Model
                    </label>
                    <select
                      id="ollama-model"
                      value={settings.llm_model}
                      onChange={e =>
                        handleChange('llm_model', e.currentTarget.value)
                      }
                      className="w-full border border-gray-300 rounded-md px-3 py-2"
                    >
                      {llmOptions.ollama.map(model => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <>
                    <div>
                      <label
                        htmlFor="openai-model"
                        className="block text-sm font-medium text-gray-700 mb-1"
                      >
                        OpenAI Model
                      </label>
                      <select
                        id="openai-model"
                        value={settings.openai_model}
                        onChange={e =>
                          handleChange('openai_model', e.currentTarget.value)
                        }
                        className="w-full border border-gray-300 rounded-md px-3 py-2"
                      >
                        {llmOptions.openai.map(model => (
                          <option key={model} value={model}>
                            {model}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label
                        htmlFor="openai-api-key"
                        className="block text-sm font-medium text-gray-700 mb-1"
                      >
                        OpenAI API Key
                      </label>
                      <input
                        id="openai-api-key"
                        type="password"
                        value={settings.openai_api_key || ''}
                        onChange={e =>
                          handleChange('openai_api_key', e.currentTarget.value)
                        }
                        className="w-full border border-gray-300 rounded-md px-3 py-2"
                        placeholder="sk-..."
                      />
                    </div>
                  </>
                )}

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="voice"
                    checked={settings.voice}
                    onChange={e =>
                      handleChange('voice', e.currentTarget.checked)
                    }
                    className="h-4 w-4 text-black focus:ring-black border-gray-300 rounded"
                  />
                  <label htmlFor="voice" className="text-sm text-gray-700">
                    Enable Voice
                  </label>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="streaming"
                    checked={settings.streaming}
                    onChange={e =>
                      handleChange('streaming', e.currentTarget.checked)
                    }
                    className="h-4 w-4 text-black focus:ring-black border-gray-300 rounded"
                  />
                  <label htmlFor="streaming" className="text-sm text-gray-700">
                    Enable Streaming
                  </label>
                </div>
              </form>
            )}

            {activeTab === 'profile' &&
              userSession?.userId &&
              profile &&
              preferences &&
              personalization &&
              privacy && (
                <div className="flex flex-col gap-4">
                  <h4 className="font-medium text-gray-800">User Profile</h4>

                  {/* User selection dropdown */}
                  <div>
                    <label
                      htmlFor="user-select"
                      className="block text-sm font-medium text-gray-700 mb-1"
                    >
                      Select User
                    </label>
                    <select
                      id="user-select"
                      value={userSession?.userId || ''}
                      onChange={e => {
                        const newUserId = e.currentTarget.value;
                        login(newUserId, userSession?.apiKey || '');
                      }}
                      className="w-full border border-gray-300 rounded-md px-3 py-2"
                    >
                      {users.map(user => (
                        <option key={user.user_id} value={user.user_id}>
                          {user.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Profile information */}
                  <div>
                    <label
                      htmlFor="profile-name"
                      className="block text-sm font-medium text-gray-700 mb-1"
                    >
                      Display Name
                    </label>
                    <input
                      id="profile-name"
                      type="text"
                      value={profile.name}
                      onChange={e =>
                        setProfile({ ...profile, name: e.currentTarget.value })
                      }
                      className="w-full border border-gray-300 rounded-md px-3 py-2"
                    />
                  </div>

                  {/* Basic profile information */}
                  <div className="mt-2">
                    <h5 className="font-medium text-sm text-gray-700 mb-2">
                      Profile Information
                    </h5>
                    <div className="text-sm text-gray-500">
                      <p>Role: {profile.role}</p>
                      <p>
                        Created:{' '}
                        {new Date(profile.created_at).toLocaleDateString()}
                      </p>
                      {profile.last_login && (
                        <p>
                          Last Login:{' '}
                          {new Date(profile.last_login).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Preferences section */}
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <h5 className="font-medium text-gray-800 mb-3">
                      Preferences
                    </h5>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label
                          htmlFor="preferred-language"
                          className="block text-sm font-medium text-gray-700 mb-1"
                        >
                          Preferred Language
                        </label>
                        <select
                          id="preferred-language"
                          value={preferences.preferred_language}
                          onChange={e =>
                            setPreferences({
                              ...preferences,
                              preferred_language: e.currentTarget.value
                            })
                          }
                          className="w-full border border-gray-300 rounded-md px-3 py-2"
                        >
                          <option value="English">English</option>
                          <option value="Spanish">Spanish</option>
                          <option value="French">French</option>
                          <option value="German">German</option>
                          <option value="Chinese">Chinese</option>
                          <option value="Japanese">Japanese</option>
                        </select>
                      </div>

                      <div>
                        <label
                          htmlFor="theme"
                          className="block text-sm font-medium text-gray-700 mb-1"
                        >
                          Theme
                        </label>
                        <select
                          id="theme"
                          value={preferences.theme}
                          onChange={e =>
                            setPreferences({
                              ...preferences,
                              theme: e.currentTarget.value
                            })
                          }
                          className="w-full border border-gray-300 rounded-md px-3 py-2"
                        >
                          <option value="system">System</option>
                          <option value="light">Light</option>
                          <option value="dark">Dark</option>
                        </select>
                      </div>

                      <div>
                        <label
                          htmlFor="font-size"
                          className="block text-sm font-medium text-gray-700 mb-1"
                        >
                          Font Size
                        </label>
                        <select
                          id="font-size"
                          value={preferences.font_size}
                          onChange={e =>
                            setPreferences({
                              ...preferences,
                              font_size: e.currentTarget.value
                            })
                          }
                          className="w-full border border-gray-300 rounded-md px-3 py-2"
                        >
                          <option value="small">Small</option>
                          <option value="medium">Medium</option>
                          <option value="large">Large</option>
                        </select>
                      </div>

                      <div>
                        <label
                          htmlFor="communication-style"
                          className="block text-sm font-medium text-gray-700 mb-1"
                        >
                          Communication Style
                        </label>
                        <input
                          id="communication-style"
                          type="text"
                          value={preferences.communication_style}
                          onChange={e =>
                            setPreferences({
                              ...preferences,
                              communication_style: e.currentTarget.value
                            })
                          }
                          className="w-full border border-gray-300 rounded-md px-3 py-2"
                          placeholder="e.g., friendly, brief, technical"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Personalization section */}
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <h5 className="font-medium text-gray-800 mb-3">
                      Personalization
                    </h5>

                    <div>
                      <label
                        htmlFor="interests"
                        className="block text-sm font-medium text-gray-700 mb-1"
                      >
                        Interests (comma-separated)
                      </label>
                      <input
                        id="interests"
                        type="text"
                        value={personalization.interests.join(', ')}
                        onChange={e => {
                          const interests = e.currentTarget.value
                            .split(',')
                            .map(i => i.trim())
                            .filter(Boolean);
                          setPersonalization({ ...personalization, interests });
                        }}
                        className="w-full border border-gray-300 rounded-md px-3 py-2"
                        placeholder="e.g., programming, AI, music"
                      />
                    </div>

                    <div className="mt-3">
                      <label
                        htmlFor="expertise"
                        className="block text-sm font-medium text-gray-700 mb-1"
                      >
                        Areas of Expertise (comma-separated)
                      </label>
                      <input
                        id="expertise"
                        type="text"
                        value={personalization.expertise.join(', ')}
                        onChange={e => {
                          const expertise = e.currentTarget.value
                            .split(',')
                            .map(i => i.trim())
                            .filter(Boolean);
                          setPersonalization({ ...personalization, expertise });
                        }}
                        className="w-full border border-gray-300 rounded-md px-3 py-2"
                        placeholder="e.g., Python, JavaScript, Machine Learning"
                      />
                    </div>

                    <div className="mt-3">
                      <label
                        htmlFor="learning-goals"
                        className="block text-sm font-medium text-gray-700 mb-1"
                      >
                        Learning Goals (comma-separated)
                      </label>
                      <input
                        id="learning-goals"
                        type="text"
                        value={personalization.learning_goals.join(', ')}
                        onChange={e => {
                          const learning_goals = e.currentTarget.value
                            .split(',')
                            .map(i => i.trim())
                            .filter(Boolean);
                          setPersonalization({
                            ...personalization,
                            learning_goals
                          });
                        }}
                        className="w-full border border-gray-300 rounded-md px-3 py-2"
                        placeholder="e.g., Learn React, Improve Python skills"
                      />
                    </div>
                  </div>

                  {/* Privacy section */}
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <h5 className="font-medium text-gray-800 mb-3">
                      Privacy Settings
                    </h5>

                    <div className="flex flex-col gap-3">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="share-conversations"
                          checked={privacy.share_conversations}
                          onChange={e =>
                            setPrivacy({
                              ...privacy,
                              share_conversations: e.currentTarget.checked
                            })
                          }
                          className="h-4 w-4 text-black focus:ring-black border-gray-300 rounded"
                        />
                        <label
                          htmlFor="share-conversations"
                          className="text-sm text-gray-700"
                        >
                          Allow sharing conversations with other users
                        </label>
                      </div>

                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="allow-analytics"
                          checked={privacy.allow_analytics}
                          onChange={e =>
                            setPrivacy({
                              ...privacy,
                              allow_analytics: e.currentTarget.checked
                            })
                          }
                          className="h-4 w-4 text-black focus:ring-black border-gray-300 rounded"
                        />
                        <label
                          htmlFor="allow-analytics"
                          className="text-sm text-gray-700"
                        >
                          Allow usage analytics
                        </label>
                      </div>

                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="store-history"
                          checked={privacy.store_history}
                          onChange={e =>
                            setPrivacy({
                              ...privacy,
                              store_history: e.currentTarget.checked
                            })
                          }
                          className="h-4 w-4 text-black focus:ring-black border-gray-300 rounded"
                        />
                        <label
                          htmlFor="store-history"
                          className="text-sm text-gray-700"
                        >
                          Store conversation history
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              )}
          </div>
        )}

        <div className="flex justify-between pt-4 mt-2 border-t border-gray-100">
          <button
            onClick={onClose}
            type="button"
            className="text-sm px-4 py-2 rounded border border-gray-200 text-gray-700 hover:bg-gray-100"
          >
            Cancel
          </button>
          <button
            type="submit"
            onClick={handleSave}
            disabled={saving || !settings}
            className="text-sm px-4 py-2 rounded bg-black text-white hover:bg-gray-900 shadow-sm disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
