import { useEffect, useState } from 'preact/hooks';
import { Settings as SettingsType, LLMOptions, useChat } from '../context/ChatContext';
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
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen]);

  const loadSettings = async () => {
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
  };

  const handleSave = async () => {
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
  };

  const handleChange = (key: keyof SettingsType, value: any) => {
    if (!settings) return;
    setSettings({ ...settings, [key]: value });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-md p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold flex items-center">
            <SettingsIcon className="h-5 w-5 mr-2" /> Settings
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {loading ? (
          <div className="text-center py-4">Loading settings...</div>
        ) : error ? (
          <div className="text-red-500 py-2">{error}</div>
        ) : settings && llmOptions ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void handleSave();
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                LLM Backend
              </label>
              <select
                value={settings.llm_backend}
                onChange={(e) => handleChange('llm_backend', e.currentTarget.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="ollama">Ollama</option>
                <option value="openai">OpenAI</option>
              </select>
            </div>

            {settings.llm_backend === 'ollama' ? (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Ollama Model
                </label>
                <select
                  value={settings.llm_model}
                  onChange={(e) => handleChange('llm_model', e.currentTarget.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {llmOptions.ollama.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    OpenAI Model
                  </label>
                  <select
                    value={settings.openai_model}
                    onChange={(e) => handleChange('openai_model', e.currentTarget.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {llmOptions.openai.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    OpenAI API Key
                  </label>
                  <input
                    type="password"
                    value={settings.openai_api_key || ''}
                    onChange={(e) => handleChange('openai_api_key', e.currentTarget.value)}
                    placeholder="sk-..."
                    className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </>
            )}

            <div className="flex items-center">
              <input
                type="checkbox"
                id="voice"
                checked={settings.voice}
                onChange={(e) => handleChange('voice', e.currentTarget.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="voice" className="ml-2 block text-sm text-gray-700">
                Enable Voice
              </label>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="streaming"
                checked={settings.streaming}
                onChange={(e) => handleChange('streaming', e.currentTarget.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="streaming" className="ml-2 block text-sm text-gray-700">
                Enable Streaming
              </label>
            </div>

            <div className="flex justify-end space-x-2 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-blue-600 border border-transparent rounded-md text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </form>
        ) : null}
      </div>
    </div>
  );
}
