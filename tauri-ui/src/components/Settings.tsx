import { useEffect, useState } from 'preact/hooks';
import {
  Settings as SettingsType,
  LLMOptions,
  useChat
} from '../context/ChatContext';
import { Settings as SettingsIcon, X } from 'lucide-preact';

interface SettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Settings({ isOpen, onClose }: SettingsProps) {
  const { getSettings, updateSettings } = useChat();
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [llmOptions, setLlmOptions] = useState<LLMOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) void loadSettings();
  }, [isOpen]);

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

  async function handleSave() {
    if (!settings) return;
    setSaving(true);
    try {
      const result = await updateSettings(settings);
      setSettings(result.settings);
      setError(null);
    } catch (err) {
      setError('Failed to save settings');
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
            <SettingsIcon className="w-5 h-5" />
            Settings{' '}
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

        {error && (
          <div className="bg-red-50 text-red-700 p-3 rounded border border-red-200 text-sm mb-4">
            {error}
          </div>
        )}

        {!loading && settings && llmOptions && (
          <form
            data-testid="settings-form"
            onSubmit={e => {
              e.preventDefault();
              void handleSave();
            }}
            className="flex flex-col gap-4 max-h-[60vh] overflow-y-auto pr-1"
          >
            <div>
              <label htmlFor="llm-backend" className="block text-sm font-medium text-gray-700 mb-1">
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
                <label htmlFor="ollama-model" className="block text-sm font-medium text-gray-700 mb-1">
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
                  <label htmlFor="openai-model" className="block text-sm font-medium text-gray-700 mb-1">
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
                  <label htmlFor="openai-api-key" className="block text-sm font-medium text-gray-700 mb-1">
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
                onChange={e => handleChange('voice', e.currentTarget.checked)}
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
