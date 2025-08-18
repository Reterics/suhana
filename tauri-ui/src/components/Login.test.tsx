import { render, screen, fireEvent, waitFor } from '@testing-library/preact';
import { describe, it, vi, expect, beforeEach, afterEach } from 'vitest';
import { Login } from './Login';

// Mock useChat to isolate the Login component behavior
const mockLogin = vi.fn();

vi.mock('../context/ChatContext.tsx', () => ({
  useChat: () => ({
    login: mockLogin
  }),
  __esModule: true
}));

const flush = () => new Promise(r => setTimeout(r, 0));

describe('Login component', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch as any;
  });

  function setup() {
    const onClose = vi.fn();
    const onSwitchToRegister = vi.fn();
    const utils = render(
      <Login onClose={onClose} onSwitchToRegister={onSwitchToRegister} />
    );
    return { onClose, onSwitchToRegister, ...utils };
  }

  it('renders fields and allows typing', async () => {
    setup();
    const userInput = screen.getByLabelText('Username') as HTMLInputElement;
    const passInput = screen.getByLabelText('Password') as HTMLInputElement;

    fireEvent.input(userInput, { target: { value: 'alice' } });
    fireEvent.input(passInput, { target: { value: 'secret' } });

    expect(userInput.value).toBe('alice');
    expect(passInput.value).toBe('secret');
  });

  it('successful login calls context.login and closes modal', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ user_id: 'u1', api_key: 'k1' })
    }) as any;

    const { onClose } = setup();

    fireEvent.input(screen.getByLabelText('Username'), { target: { value: 'bob' } });
    fireEvent.input(screen.getByLabelText('Password'), { target: { value: 'pw' } });

    fireEvent.submit(screen.getByRole('button', { name: /login/i }));

    await waitFor(() => expect(mockLogin).toHaveBeenCalledWith('u1', 'k1'));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows error when server returns non-ok', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, text: async () => 'invalid credentials' }) as any;

    setup();

    fireEvent.input(screen.getByLabelText('Username'), { target: { value: 'bad' } });
    fireEvent.input(screen.getByLabelText('Password'), { target: { value: 'user' } });

    fireEvent.submit(screen.getByRole('button', { name: /login/i }));

    expect(await screen.findByText(/Login failed: invalid credentials/i)).toBeInTheDocument();
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('disables submit and shows loading text while pending', async () => {
    let resolveFn: (v?: any) => void;
    const pending = new Promise(res => (resolveFn = res));
    globalThis.fetch = vi.fn().mockReturnValue(pending) as any;

    setup();

    fireEvent.input(screen.getByLabelText('Username'), { target: { value: 'x' } });
    fireEvent.input(screen.getByLabelText('Password'), { target: { value: 'y' } });

    const submitBtn = screen.getByRole('button', { name: /login/i });
    fireEvent.submit(submitBtn);

    // Button should switch to loading state
    await waitFor(() => expect(submitBtn).toBeDisabled());
    expect(submitBtn).toHaveTextContent(/Logging in.../i);

    // Resolve pending request and ensure it re-enables (will error due to missing ok, but we only care about disabled state toggling)
    // Fulfill with a minimal ok response to complete gracefully
    // @ts-expect-error resolveFn defined above
    resolveFn({ ok: true, json: async () => ({ user_id: 'u', api_key: 'k' }) });
    await flush();

    await waitFor(() => expect(submitBtn).not.toBeDisabled());
  });

  it('clicking Register triggers onSwitchToRegister', async () => {
    const { onSwitchToRegister } = setup();
    const regBtn = screen.getByRole('button', { name: 'Register' });
    fireEvent.click(regBtn);
    expect(onSwitchToRegister).toHaveBeenCalled();
  });

  it('backdrop click closes, inner click does not', async () => {
    const { onClose, container } = setup();

    // Click on inner content first — should not close
    const modalPanel = container.querySelector('.max-w-md') as HTMLElement;
    fireEvent.click(modalPanel);
    expect(onClose).not.toHaveBeenCalled();

    // Click on backdrop — should close
    const backdrop = container.firstElementChild as HTMLElement; // outer div with fixed inset-0
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });
});
