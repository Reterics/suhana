import { render, screen, fireEvent, waitFor } from '@testing-library/preact';
import { describe, it, vi, expect, beforeEach } from 'vitest';
import { Settings } from './Settings';

// Provide a lightweight mock ChatContext aligned with the current component API
let mockSettings: any;
const mockUpdateSettings = vi.fn();

vi.mock('../context/ChatContext.tsx', () => ({
  useChat: () => ({
    settings: mockSettings,
    updateSettings: mockUpdateSettings,
    // Minimal stubs for profile APIs not used in these tests
    userSession: null,
    login: vi.fn(),
    getUsers: vi.fn(),
    getProfile: vi.fn(),
    updateProfile: vi.fn(),
    getPreferences: vi.fn(),
    updatePreferences: vi.fn(),
    getPersonalization: vi.fn(),
    updatePersonalization: vi.fn(),
    getPrivacySettings: vi.fn(),
    updatePrivacySettings: vi.fn()
  }),
  __esModule: true
}));

beforeEach(() => {
  mockSettings = {
    settings: {
      llm_backend: 'ollama',
      llm_model: 'llama2',
      openai_model: 'gpt-4',
      openai_api_key: 'sk-test',
      voice: true,
      streaming: false,
      secured_streaming: false
    },
    llm_options: {
      ollama: ['llama2', 'llama3'],
      openai: ['gpt-3.5', 'gpt-4']
    }
  };
  vi.clearAllMocks();
});


describe('Settings Component - Full Coverage', () => {
  it('renders and displays ollama UI', async () => {
    render(<Settings onClose={vi.fn()} />);
    expect(await screen.findByLabelText('LLM Backend')).toBeInTheDocument();
    expect(screen.getByLabelText('Ollama Model')).toBeInTheDocument();
    expect(screen.getByLabelText('Enable Voice')).toBeChecked();
    expect(screen.getByLabelText('Enable Streaming')).not.toBeChecked();
  });

  it('switches to openai and shows correct UI', async () => {
    // Switch mocked settings before render
    mockSettings.settings.llm_backend = 'openai';
    render(<Settings onClose={vi.fn()} />);
    expect(await screen.findByLabelText('LLM Backend')).toHaveValue('openai');
    expect(screen.getByLabelText('OpenAI Model')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('sk-...')).toHaveValue('sk-test');
  });

  it('handles checkbox toggles correctly', async () => {
    render(<Settings onClose={vi.fn()} />);
    const voiceCheckbox = await screen.findByLabelText('Enable Voice');
    const streamCheckbox = screen.getByLabelText('Enable Streaming');

    fireEvent.click(voiceCheckbox);
    fireEvent.click(streamCheckbox);

    expect(voiceCheckbox).not.toBeChecked();
    expect(streamCheckbox).toBeChecked();
  });

  it('handles save successfully', async () => {
    render(<Settings onClose={vi.fn()} />);
    const saveBtn = await screen.findByRole('button', { name: 'Save' });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockUpdateSettings).toHaveBeenCalledWith(mockSettings);
    });
  });

  it('shows error if save fails', async () => {
    mockUpdateSettings.mockRejectedValueOnce(new Error('Save failed'));

    render(<Settings onClose={vi.fn()} />);
    const saveBtn = await screen.findByRole('button', { name: 'Save' });
    fireEvent.click(saveBtn);

    expect(
      await screen.findByText(/Failed to save settings/i)
    ).toBeInTheDocument();
  });

  it('calls onClose on cancel', async () => {
    const onClose = vi.fn();
    render(<Settings onClose={onClose} />);
    const cancelBtn = await screen.findByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelBtn);
    expect(onClose).toHaveBeenCalled();
  });

  it('submits form via fireEvent.submit()', async () => {
    render(<Settings onClose={vi.fn()} />);

    await screen.findByLabelText('LLM Backend');

    fireEvent.submit(screen.getByTestId('settings-form'));

    await waitFor(() => {
      expect(mockUpdateSettings).toHaveBeenCalled();
    });
  });
});
