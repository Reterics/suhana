import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/preact';
import WelcomeScreen from './WelcomePage';

// Mock motion/react so motion.* render as plain elements without forwarding refs
vi.mock('motion/react', () => ({
  motion: {
    div: (props: any) => <div {...props} />, // no ref forwarding
    img: (props: any) => <img {...props} />, // no ref forwarding
    h1: (props: any) => <h1 {...props} />,
    p: (props: any) => <p {...props} />,
  },
}));

// Mock icons and svg-react imports to lightweight components
vi.mock('lucide-preact', () => ({
  SendHorizontal: (props: any) => <svg data-testid="send-icon" {...props} />,
  Settings: (props: any) => <svg data-testid="settings-icon" {...props} />,
}));
vi.mock('../assets/microphone.svg?react', () => ({
  default: (props: any) => <svg data-testid="mic-icon" {...props} />,
}));

describe('WelcomeScreen', () => {
  let setGuestMode: ReturnType<typeof vi.fn>;
  let setInitialInput: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    setGuestMode = vi.fn();
    setInitialInput = vi.fn();
  });

  it('renders heading and UI elements', () => {
    render(
      <WelcomeScreen
        setGuestMode={setGuestMode}
        setInitialInput={setInitialInput}
        examplePrompts={[
          'Generate unit tests for my React hook',
          'Why is my Docker build slow?',
        ]}
      />
    );

    expect(screen.getByRole('heading', { name: /welcome to suhana/i })).toBeTruthy();
    const textarea = screen.getByPlaceholderText('Ask anything to start a guest chat…');
    expect(textarea).toBeTruthy();

    // Example prompt buttons
    expect(screen.getByRole('button', { name: /generate unit tests for my react hook/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /why is my docker build slow\?/i })).toBeTruthy();

    // Icons are rendered (from mocks)
    expect(screen.getByTestId('mic-icon')).toBeTruthy();
    expect(screen.getByTestId('settings-icon')).toBeTruthy();
    expect(screen.getByTestId('send-icon')).toBeTruthy();
  });

  it('starts chat when clicking an example prompt (immediate path without motion refs)', () => {
    const prompt = 'Explain event loop';
    render(
      <WelcomeScreen
        setGuestMode={setGuestMode}
        setInitialInput={setInitialInput}
        examplePrompts={[prompt]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: prompt }));

    // Should pass prompt to initial input and immediately proceed to guest mode
    expect(setInitialInput).toHaveBeenCalledWith(prompt);
    expect(setGuestMode).toHaveBeenCalledWith(true);
  });

  it('sends the typed value when clicking Send', () => {
    render(
      <WelcomeScreen setGuestMode={setGuestMode} setInitialInput={setInitialInput} />
    );

    const textarea = screen.getByPlaceholderText('Ask anything to start a guest chat…') as HTMLTextAreaElement;

    // Update value via keyUp handler (component reads from currentTarget on keyUp)
    textarea.value = '  hello world  ';
    fireEvent.keyUp(textarea);

    fireEvent.click(screen.getByTitle('Send'));

    expect(setInitialInput).toHaveBeenCalledWith('hello world');
    expect(setGuestMode).toHaveBeenCalledWith(true);
  });

  it('focusing the textarea triggers entering guest mode', () => {
    render(
      <WelcomeScreen setGuestMode={setGuestMode} setInitialInput={setInitialInput} />
    );

    const textarea = screen.getByPlaceholderText('Ask anything to start a guest chat…');

    // set a value first so startChat(value) passes non-empty string
    (textarea as HTMLTextAreaElement).value = 'Focus to start';
    fireEvent.keyUp(textarea);

    fireEvent.focus(textarea);

    expect(setInitialInput).toHaveBeenCalledWith('Focus to start');
    expect(setGuestMode).toHaveBeenCalledWith(true);
  });
});
