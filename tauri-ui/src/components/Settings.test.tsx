import { render, screen, fireEvent, waitFor } from '@testing-library/preact';
import { describe, it, vi, expect, beforeEach } from 'vitest';
import { Settings } from './Settings';

// Provide a lightweight but flexible mock ChatContext aligned with the current component API
let mockSettings: any;
const mockUpdateSettings = vi.fn();

// Mocks for Profile tab flows (overridable per test)
let mockUserSession: any = null;
const mockLogin = vi.fn();
const mockGetUsers = vi.fn();
const mockGetProfile = vi.fn();
const mockUpdateProfile = vi.fn();
const mockGetPreferences = vi.fn();
const mockUpdatePreferences = vi.fn();
const mockGetPersonalization = vi.fn();
const mockUpdatePersonalization = vi.fn();
const mockGetPrivacySettings = vi.fn();
const mockUpdatePrivacySettings = vi.fn();

vi.mock('../context/ChatContext.tsx', () => ({
  useChat: () => ({
    settings: mockSettings,
    updateSettings: mockUpdateSettings,

    userSession: mockUserSession,
    login: mockLogin,

    getUsers: mockGetUsers,
    getProfile: mockGetProfile,
    updateProfile: mockUpdateProfile,
    getPreferences: mockGetPreferences,
    updatePreferences: mockUpdatePreferences,
    getPersonalization: mockGetPersonalization,
    updatePersonalization: mockUpdatePersonalization,
    getPrivacySettings: mockGetPrivacySettings,
    updatePrivacySettings: mockUpdatePrivacySettings
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



describe('Settings Component - Profile Tab', () => {
  beforeEach(() => {
    // Default user session for profile flows
    mockUserSession = { userId: 'u1', apiKey: 'k', lastLogin: new Date() } as any;

    // Default profile-related mock returns
    const baseProfile = {
      name: 'Alice',
      created_at: '2025-01-01T00:00:00',
      last_login: null,
      role: 'user',
      avatar: null,
      preferences: {} as any,
      personalization: {} as any,
      privacy: {} as any,
      history: []
    };

    mockGetProfile.mockResolvedValue({ profile: baseProfile });
    mockGetPreferences.mockResolvedValue({
      preferences: {
        preferred_language: 'English',
        communication_style: 'friendly',
        focus: 'general',
        theme: 'system',
        font_size: 'medium',
        notification_level: 'all',
        timezone: 'UTC',
        date_format: 'YYYY-MM-DD',
        time_format: '24h'
      }
    });
    mockGetPersonalization.mockResolvedValue({
      personalization: {
        interests: ['programming'],
        expertise: ['js'],
        learning_goals: ['react'],
        favorite_tools: [],
        custom_shortcuts: {}
      }
    });
    mockGetPrivacySettings.mockResolvedValue({
      privacy: {
        share_conversations: true,
        allow_analytics: false,
        store_history: true
      }
    });

    mockGetUsers.mockResolvedValue({ users: [] });

    mockUpdateProfile.mockResolvedValue({});
    mockUpdatePreferences.mockResolvedValue({});
    mockUpdatePersonalization.mockResolvedValue({});
    mockUpdatePrivacySettings.mockResolvedValue({});
  });

  it('loads profile section, edits values, and saves via update* calls', async () => {
    render(<Settings onClose={vi.fn()} />);

    // Navigate to User Profile tab
    fireEvent.click(await screen.findByRole('button', { name: 'User Profile' }));

    // Wait for profile form to appear
    const nameInput = await screen.findByLabelText('Display Name');
    expect(nameInput).toHaveValue('Alice');

    // Edit profile name (component uses onChange)
    fireEvent.change(nameInput as HTMLInputElement, { target: { value: 'Alice B' } });

    // Change a preference
    const languageSelect = screen.getByLabelText('Preferred Language') as HTMLSelectElement;
    fireEvent.change(languageSelect, { target: { value: 'Spanish' } });

    // Update personalization interests (component uses onChange)
    const interestsInput = screen.getByLabelText('Interests (comma-separated)');
    fireEvent.change(interestsInput as HTMLInputElement, { target: { value: 'programming, music' } });

    // Toggle a privacy checkbox
    const shareCbx = screen.getByLabelText('Allow sharing conversations with other users') as HTMLInputElement;
    fireEvent.click(shareCbx); // was true -> becomes false

    // Ensure the input value reflects the change before saving
    await waitFor(() => expect(screen.getByLabelText('Display Name')).toHaveValue('Alice B'));

    // Save
    const saveBtn = screen.getByRole('button', { name: 'Save' });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockUpdateProfile).toHaveBeenCalledWith('u1', { name: 'Alice B' });
      expect(mockUpdatePreferences).toHaveBeenCalledWith('u1', expect.objectContaining({ preferred_language: 'Spanish' }));
      expect(mockUpdatePersonalization).toHaveBeenCalledWith('u1', expect.objectContaining({ interests: ['programming', 'music'] }));
      expect(mockUpdatePrivacySettings).toHaveBeenCalledWith('u1', expect.objectContaining({ share_conversations: false }));
    });
  });

  it('shows admin-specific UI: Register User tab and user selector; switching user calls login', async () => {
    // Admin profile and users list
    mockGetProfile.mockResolvedValueOnce({ profile: { name: 'Root', created_at: '2025-01-01', last_login: null, role: 'admin', avatar: null, preferences: {}, personalization: {}, privacy: {}, history: [] } });
    mockGetUsers.mockResolvedValueOnce({ users: [ { user_id: 'u1', name: 'Alice' }, { user_id: 'u2', name: 'Bob' } ] });

    render(<Settings onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: 'User Profile' }));

    // Register User tab visible
    expect(await screen.findByRole('button', { name: 'Register User' })).toBeInTheDocument();

    // User select visible and change triggers login
    const userSelect = await screen.findByLabelText('Select User');
    fireEvent.change(userSelect as HTMLSelectElement, { target: { value: 'u2' } });
    await waitFor(() => expect(mockLogin).toHaveBeenCalledWith('u2', 'k'));
  });

  it('handles profile save error and shows error message', async () => {
    mockUpdateProfile.mockRejectedValueOnce(new Error('boom'));

    render(<Settings onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'User Profile' }));

    const saveBtn = await screen.findByRole('button', { name: 'Save' });
    fireEvent.click(saveBtn);

    expect(await screen.findByText(/Failed to save profile/i)).toBeInTheDocument();
  });
});


describe('Settings Component - Streaming exclusivity', () => {
  it('enforces mutual exclusivity between streaming and secured_streaming', async () => {
    mockSettings.settings.streaming = false;
    mockSettings.settings.secured_streaming = false;

    render(<Settings onClose={vi.fn()} />);

    const streamingCbx = await screen.findByLabelText('Enable Streaming');
    const securedCbx = screen.getByLabelText('Enable Secured Streaming');

    // Enable secured streaming -> streaming checkbox should get disabled
    fireEvent.click(securedCbx);
    expect((securedCbx as HTMLInputElement).checked).toBe(true);
    expect((streamingCbx as HTMLInputElement).disabled).toBe(true);

    // Now uncheck secured and enable streaming -> secured should be disabled
    fireEvent.click(securedCbx); // uncheck
    fireEvent.click(streamingCbx); // check streaming
    expect((streamingCbx as HTMLInputElement).checked).toBe(true);
    expect((securedCbx as HTMLInputElement).disabled).toBe(true);
  });
});
