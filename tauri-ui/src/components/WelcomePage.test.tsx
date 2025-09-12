import { render, screen, fireEvent, waitFor } from '@testing-library/preact';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import WelcomeScreen from './WelcomePage';

function setup(extraProps: Partial<Parameters<typeof WelcomeScreen>[0]> = {}) {
  const handleSendMessage = vi.fn().mockResolvedValue(undefined);
  const setGuestMode = vi.fn();
  const navigateToChat = vi.fn();

  const utils = render(
    <WelcomeScreen
      handleSendMessage={handleSendMessage}
      setGuestMode={setGuestMode}
      navigateToChat={navigateToChat}
      {...extraProps}
    />
  );

  return { handleSendMessage, setGuestMode, navigateToChat, ...utils };
}

describe('WelcomePage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders heading, help text and example prompts', () => {
    setup();
    expect(screen.getByRole('heading', { name: /welcome to suhana/i })).toBeInTheDocument();
    expect(screen.getByText(/your intelligent assistant/i)).toBeInTheDocument();
    // default example prompts
    const chips = screen.getAllByRole('button', { name: /summarize|generate unit tests|docker build/i });
    expect(chips.length).toBeGreaterThanOrEqual(3);
  });

  it('clicking big CTA starts guest chat without sending a message', async () => {
    const { setGuestMode, navigateToChat, handleSendMessage } = setup();

    const bigCta = screen.getByRole('button', { name: /start chat/i });
    fireEvent.click(bigCta);

    await waitFor(() => expect(setGuestMode).toHaveBeenCalledWith(true));
    expect(handleSendMessage).not.toHaveBeenCalled();
    expect(navigateToChat).toHaveBeenCalledTimes(1);
  });

  it('pressing Enter on big CTA also starts chat', async () => {
    const { navigateToChat } = setup();
    const bigCta = screen.getByRole('button', { name: /start chat/i });

    fireEvent.keyDown(bigCta, { key: 'Enter' });

    await waitFor(() => expect(navigateToChat).toHaveBeenCalledTimes(1));
  });

  it('clicking an example prompt sends that prompt and navigates', async () => {
    const { handleSendMessage, navigateToChat } = setup({ examplePrompts: ['Say hi'] });

    const chip = screen.getByRole('button', { name: 'Say hi' });
    fireEvent.click(chip);

    await waitFor(() => expect(handleSendMessage).toHaveBeenCalledWith('Say hi'));
    expect(navigateToChat).toHaveBeenCalledTimes(1);
  });


  it('focusing the input navigates without sending a message', async () => {
    const { navigateToChat, handleSendMessage } = setup();

    const input = screen.getByLabelText(/ask anything to start a guest chat/i);
    fireEvent.focus(input);

    await waitFor(() => expect(navigateToChat).toHaveBeenCalledTimes(1));
    expect(handleSendMessage).not.toHaveBeenCalled();
  });

  it('Start button uses current value or no sending', async () => {
    const { handleSendMessage, navigateToChat } = setup();

    const startBtn = screen.getByRole('button', { name: 'Start' });
    const input = screen.getByPlaceholderText(/ask anything to start a guest chat/i) as HTMLInputElement;
    fireEvent.input(input, { target: { value: 'Hello' } });

    fireEvent.click(startBtn);
    await waitFor(() => expect(handleSendMessage).toHaveBeenCalledWith('Hello'));
    expect(navigateToChat).toHaveBeenCalledTimes(1);


    fireEvent.click(startBtn);

    expect(navigateToChat).toHaveBeenCalledTimes(1);
  });
});
