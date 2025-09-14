import { render, screen, fireEvent, waitFor } from '@testing-library/preact';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock motion/react so motion.div renders as a plain div without forwarding ref
vi.mock('motion/react', () => ({
  motion: {
    // Do not forward ref to force immediate proceedStartChat path in component
    div: (props: any) => <div {...props} />,
  },
}));

import WelcomeScreen from './WelcomePage';

function setup(extraProps: Partial<Parameters<typeof WelcomeScreen>[0]> = {}) {
  const setGuestMode = vi.fn();
  const setInitialInput = vi.fn();
  const navigateToChat = vi.fn();

  const utils = render(
    <WelcomeScreen
      setGuestMode={setGuestMode}
      setInitialInput={setInitialInput}
      navigateToChat={navigateToChat}
      {...extraProps}
    />
  );

  return { setGuestMode, setInitialInput, navigateToChat, ...utils };
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

  it('clicking an example prompt sets initial input and navigates', async () => {
    const { setInitialInput, navigateToChat, setGuestMode } = setup({ examplePrompts: ['Say hi'] });

    const chip = screen.getByRole('button', { name: 'Say hi' });
    fireEvent.click(chip);

    await waitFor(() => expect(setGuestMode).toHaveBeenCalledWith(true));
    expect(setInitialInput).toHaveBeenCalledWith('Say hi');
    expect(navigateToChat).toHaveBeenCalledTimes(1);
  });

  it('focusing the input navigates without a prompt (empty initial input)', async () => {
    const { navigateToChat, setInitialInput, setGuestMode } = setup();

    const input = screen.getByLabelText(/ask anything to start a guest chat/i);
    fireEvent.focus(input);

    await waitFor(() => expect(setGuestMode).toHaveBeenCalledWith(true));
    expect(setInitialInput).toHaveBeenCalledWith('');
    expect(navigateToChat).toHaveBeenCalledTimes(1);
  });

});
