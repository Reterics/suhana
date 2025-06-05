import {render, screen, fireEvent, waitFor} from '@testing-library/preact';
import {describe, it, vi, expect, beforeEach} from 'vitest';
import {Settings} from './Settings';
import {useChat} from '../context/ChatContext';

vi.mock('../context/ChatContext', async () => {
  const actual = await vi.importActual('../context/ChatContext');
  return {
    ...actual,
    useChat: vi.fn()
  };
});

const mockGetSettings = vi.fn();
const mockUpdateSettings = vi.fn();

beforeEach(() => {
  (useChat as any).mockReturnValue({
    getSettings: mockGetSettings,
    updateSettings: mockUpdateSettings
  });
});

const baseSettings = {
  llm_backend: 'ollama',
  llm_model: 'llama2',
  openai_model: 'gpt-4',
  openai_api_key: 'sk-test',
  voice: true,
  streaming: false
};

const llmOptions = {
  ollama: ['llama2', 'llama3'],
  openai: ['gpt-3.5', 'gpt-4']
};

describe('Settings Component - Full Coverage', () => {
  it('renders and displays ollama UI', async () => {
    mockGetSettings.mockResolvedValueOnce({
      settings: baseSettings,
      llm_options: llmOptions
    });

    render(<Settings isOpen={true} onClose={vi.fn()}/>);
    expect(await screen.findByLabelText('LLM Backend')).toBeInTheDocument();
    expect(screen.getByLabelText('Ollama Model')).toBeInTheDocument();
    expect(screen.getByLabelText('Enable Voice')).toBeChecked();
    expect(screen.getByLabelText('Enable Streaming')).not.toBeChecked();
  });

  it('switches to openai and shows correct UI', async () => {
    mockGetSettings.mockResolvedValueOnce({
      settings: {...baseSettings, llm_backend: 'openai'},
      llm_options: llmOptions
    });

    render(<Settings isOpen={true} onClose={vi.fn()}/>);
    expect(await screen.findByLabelText('LLM Backend')).toHaveValue('openai');
    expect(screen.getByLabelText('OpenAI Model')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('sk-...')).toHaveValue('sk-test');
  });

  it('handles checkbox toggles correctly', async () => {
    mockGetSettings.mockResolvedValueOnce({
      settings: baseSettings,
      llm_options: llmOptions
    });

    render(<Settings isOpen={true} onClose={vi.fn()}/>);
    const voiceCheckbox = await screen.findByLabelText('Enable Voice');
    const streamCheckbox = screen.getByLabelText('Enable Streaming');

    fireEvent.click(voiceCheckbox);
    fireEvent.click(streamCheckbox);

    expect(voiceCheckbox).not.toBeChecked();
    expect(streamCheckbox).toBeChecked();
  });

  it('handles save successfully', async () => {
    mockGetSettings.mockResolvedValueOnce({
      settings: baseSettings,
      llm_options: llmOptions
    });
    mockUpdateSettings.mockResolvedValueOnce({
      settings: baseSettings
    });

    render(<Settings isOpen={true} onClose={vi.fn()}/>);
    const saveBtn = await screen.findByRole('button', {name: 'Save'});
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockUpdateSettings).toHaveBeenCalledWith(baseSettings);
    });
  });

  it('shows error if settings load fails', async () => {
    mockGetSettings.mockRejectedValueOnce(new Error('Load failed'));

    render(<Settings isOpen={true} onClose={vi.fn()}/>);
    expect(await screen.findByText(/failed to load settings/i)).toBeInTheDocument();
  });

  it('shows error if save fails', async () => {
    mockGetSettings.mockResolvedValueOnce({
      settings: baseSettings,
      llm_options: llmOptions
    });
    mockUpdateSettings.mockRejectedValueOnce(new Error('Save failed'));

    render(<Settings isOpen={true} onClose={vi.fn()}/>);
    const saveBtn = await screen.findByRole('button', {name: 'Save'});
    fireEvent.click(saveBtn);

    expect(await screen.findByText(/failed to save settings/i)).toBeInTheDocument();
  });

  it('calls onClose on cancel', async () => {
    const onClose = vi.fn();
    mockGetSettings.mockResolvedValueOnce({
      settings: baseSettings,
      llm_options: llmOptions
    });

    render(<Settings isOpen={true} onClose={onClose}/>);
    const cancelBtn = await screen.findByRole('button', {name: 'Cancel'});
    fireEvent.click(cancelBtn);
    expect(onClose).toHaveBeenCalled();
  });

  it('renders nothing when isOpen is false', () => {
    const {container} = render(<Settings isOpen={false} onClose={vi.fn()}/>);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows error if save fails', async () => {
    mockGetSettings.mockResolvedValueOnce({
      settings: baseSettings,
      llm_options: llmOptions
    });
    mockUpdateSettings.mockRejectedValueOnce(new Error('Save failed'));

    render(<Settings isOpen={true} onClose={vi.fn()}/>);
    fireEvent.click(await screen.findByRole('button', {name: 'Save'}));

    expect(await screen.findByText(/failed to save settings/i)).toBeInTheDocument();
  });

  it('submits form via fireEvent.submit()', async () => {
    mockGetSettings.mockResolvedValueOnce({
      settings: {
        llm_backend: 'ollama',
        llm_model: 'llama2',
        openai_model: 'gpt-4',
        openai_api_key: 'sk-test',
        voice: true,
        streaming: false
      },
      llm_options: {
        ollama: ['llama2', 'llama3'],
        openai: ['gpt-3.5', 'gpt-4']
      }
    });

    mockUpdateSettings.mockResolvedValueOnce({
      settings: {
        llm_backend: 'ollama',
        llm_model: 'llama2',
        openai_model: 'gpt-4',
        openai_api_key: 'sk-test',
        voice: true,
        streaming: false
      }
    });

    render(<Settings isOpen={true} onClose={vi.fn()}/>);

    await screen.findByLabelText('LLM Backend');

    fireEvent.submit(screen.getByTestId('settings-form'));

    await waitFor(() => {
      expect(mockUpdateSettings).toHaveBeenCalled();
    });
  });

  it('does not crash if handleSave called with no settings', async () => {
    (useChat as any).mockReturnValueOnce({
      getSettings: vi.fn().mockResolvedValue({settings: null, llm_options: null}),
      updateSettings: vi.fn()
    });

    render(<Settings isOpen={true} onClose={vi.fn()}/>);
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
  });
});
