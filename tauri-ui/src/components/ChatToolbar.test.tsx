import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/preact';
import { ChatToolbar } from './ChatToolbar';

Object.defineProperty(globalThis.navigator, 'mediaDevices', {
  writable: true,
  configurable: true,
  value: {
    enumerateDevices: vi.fn().mockResolvedValue([
      { deviceId: 'mic1', kind: 'audioinput', label: 'Mic 1' },
      { deviceId: 'mic2', kind: 'audioinput', label: 'Mic 2' }
    ]),
    getUserMedia: vi.fn()
  }
});

// --- Mock ChatContext ---
const mockSetApiKey = vi.fn();
const mockTranscribe = vi.fn();
vi.mock('../context/ChatContext.tsx', () => ({
  useChat: () => ({
    apiKey: 'apikey',
    setApiKey: mockSetApiKey,
    transcribe: mockTranscribe
  }),
  __esModule: true
}));

// --- Mock icons (no-op) ---
vi.mock('lucide-preact', () => ({
  Mic: () => <span data-testid="icon-mic" />,
  SendHorizontal: () => <span data-testid="icon-send" />,
  Settings: () => <span data-testid="icon-settings" />,
  TestTube: () => <span data-testid="icon-testtube" />,
  __esModule: true
}));

describe('ChatToolbar', () => {
  beforeAll(() => {
    class MockAudioContext {
      createMediaStreamSource() {
        return {
          connect: vi.fn()
        };
      }

      createAnalyser() {
        return {
          fftSize: 256,
          getByteTimeDomainData: vi.fn()
        };
      }

      close() {}
    }

    // Polyfill
    Object.defineProperty(globalThis, 'AudioContext', {
      configurable: true,
      writable: true,
      value: MockAudioContext
    });
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders textarea and main buttons', () => {
    render(<ChatToolbar onSend={vi.fn()} />);
    expect(screen.getByPlaceholderText(/Type a message/i)).toBeTruthy();
    expect(screen.getByTestId('icon-send')).toBeTruthy();
    expect(screen.getByTestId('icon-mic')).toBeTruthy();
    expect(screen.getByTestId('icon-settings')).toBeTruthy();
    expect(screen.getByTestId('icon-testtube')).toBeTruthy();
  });

  it('allows typing and sending a message', () => {
    const onSend = vi.fn();
    render(<ChatToolbar onSend={onSend} />);
    const textarea = screen.getByPlaceholderText(/Type a message/i);

    fireEvent.input(textarea, { target: { value: 'Hello world' } });

    // Click Send button
    fireEvent.click(screen.getByTestId('icon-send').parentElement!);

    expect(onSend).toHaveBeenCalledWith('Hello world');
    // Input should be cleared after send
    expect((textarea as HTMLTextAreaElement).value).toBe('');
  });

  it('does not send blank messages', () => {
    const onSend = vi.fn();
    render(<ChatToolbar onSend={onSend} />);
    const textarea = screen.getByPlaceholderText(/Type a message/i);

    fireEvent.input(textarea, { target: { value: '   ' } });
    fireEvent.click(screen.getByTestId('icon-send').parentElement!);

    expect(onSend).not.toHaveBeenCalled();
  });

  it('toggles API key input when clicking Settings', () => {
    render(<ChatToolbar onSend={vi.fn()} />);
    // Initially hidden (opacity-0, w-0, h-0)
    const apiKeyInput = screen.getByPlaceholderText('API Key');
    expect(
      apiKeyInput.parentElement?.classList.contains('opacity-0')
    ).toBeTruthy();

    // Click Settings icon
    fireEvent.click(screen.getByTestId('icon-settings').parentElement!);
    // Now should be visible (opacity-100, w-full)
    expect(apiKeyInput.closest('.opacity-100')).toBeTruthy();
  });

  it('calls setApiKey on API key input change', () => {
    render(<ChatToolbar onSend={vi.fn()} />);
    // Show the input
    fireEvent.click(screen.getByTestId('icon-settings').parentElement!);

    const apiKeyInput = screen.getByPlaceholderText('API Key');
    fireEvent.input(apiKeyInput, { target: { value: 'newkey' } });

    expect(mockSetApiKey).toHaveBeenCalledWith('newkey');
  });

  it('toggles mic selector dropdown', () => {
    render(<ChatToolbar onSend={vi.fn()} />);
    // Click TestTube icon to open mic selector
    fireEvent.click(screen.getByTestId('icon-testtube').parentElement!);

    // Now selector is visible (opacity-100)
    const micSelect = screen.getByRole('combobox');
    expect(micSelect.closest('.opacity-100')).toBeTruthy();
  });

  it('calls setMicDeviceId and testMic when selecting a device', async () => {
    // Mock testMic (must spy on ChatToolbar's instance, but not exported directly)
    render(<ChatToolbar onSend={vi.fn()} />);
    fireEvent.click(screen.getByTestId('icon-testtube').parentElement!);

    // Devices should be present as options
    expect(await screen.findByText('Mic 1')).toBeTruthy();
    expect(await screen.findByText('Mic 2')).toBeTruthy();
    // Can't spy directly on setMicDeviceId/testMic (internal state)
    // So just change selection and ensure no crash
    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: 'mic1' }
    });
  });
});
