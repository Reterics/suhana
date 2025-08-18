import { render, screen, fireEvent, waitFor } from '@testing-library/preact';
import { describe, it, vi, expect, beforeEach } from 'vitest';
import { Register } from './Register';

// Mock ChatContext to isolate Register behavior
const mockRegisterUser = vi.fn();
const mockLogin = vi.fn();

vi.mock('../context/ChatContext.tsx', () => ({
  useChat: () => ({
    registerUser: mockRegisterUser,
    login: mockLogin
  }),
  __esModule: true
}));

const flush = () => new Promise(r => setTimeout(r, 0));

function setup() {
  const onClose = vi.fn();
  const onSwitchToLogin = vi.fn();
  const utils = render(
    <Register onClose={onClose} onSwitchToLogin={onSwitchToLogin} />
  );
  return { onClose, onSwitchToLogin, ...utils };
}

describe('Register component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders fields and allows typing', async () => {
    setup();

    const userInput = screen.getByLabelText('Username') as HTMLInputElement;
    const nameInput = screen.getByLabelText('Display Name (optional)') as HTMLInputElement;
    const passInput = screen.getByLabelText('Password') as HTMLInputElement;
    const confirmInput = screen.getByLabelText('Confirm Password') as HTMLInputElement;

    fireEvent.input(userInput, { target: { value: 'alice_1' } });
    fireEvent.input(nameInput, { target: { value: 'Alice' } });
    fireEvent.input(passInput, { target: { value: 'secret' } });
    fireEvent.input(confirmInput, { target: { value: 'secret' } });

    expect(userInput.value).toBe('alice_1');
    expect(nameInput.value).toBe('Alice');
    expect(passInput.value).toBe('secret');
    expect(confirmInput.value).toBe('secret');
  });

  it('shows error when passwords do not match and prevents submit', async () => {
    setup();

    fireEvent.input(screen.getByLabelText('Username'), { target: { value: 'bob' } });
    fireEvent.input(screen.getByLabelText('Password'), { target: { value: 'pw1' } });
    fireEvent.input(screen.getByLabelText('Confirm Password'), { target: { value: 'pw2' } });

    const submitBtn = screen.getByRole('button', { name: 'Register' });
    fireEvent.submit(submitBtn);

    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument();
    expect(mockRegisterUser).not.toHaveBeenCalled();
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('successful registration calls registerUser then login and closes modal', async () => {
    mockRegisterUser.mockResolvedValueOnce({ user_id: 'u1', api_key: 'k1' });

    const { onClose } = setup();

    fireEvent.input(screen.getByLabelText('Username'), { target: { value: 'newuser' } });
    fireEvent.input(screen.getByLabelText('Display Name (optional)'), { target: { value: 'New User' } });
    fireEvent.input(screen.getByLabelText('Password'), { target: { value: 'pw' } });
    fireEvent.input(screen.getByLabelText('Confirm Password'), { target: { value: 'pw' } });

    const submitBtn = screen.getByRole('button', { name: 'Register' });
    fireEvent.submit(submitBtn);

    await waitFor(() => expect(mockRegisterUser).toHaveBeenCalledWith('newuser', 'pw', 'New User'));
    expect(mockLogin).toHaveBeenCalledWith('u1', 'k1');
    expect(onClose).toHaveBeenCalled();
  });

  it('disables submit and shows "Registering..." while pending', async () => {
    let resolveFn: (v?: any) => void;
    const pending = new Promise(res => (resolveFn = res));
    mockRegisterUser.mockReturnValueOnce(pending as any);

    setup();

    fireEvent.input(screen.getByLabelText('Username'), { target: { value: 'x' } });
    fireEvent.input(screen.getByLabelText('Password'), { target: { value: 'y' } });
    fireEvent.input(screen.getByLabelText('Confirm Password'), { target: { value: 'y' } });

    const submitBtn = screen.getByRole('button', { name: 'Register' });
    fireEvent.submit(submitBtn);

    await waitFor(() => expect(submitBtn).toBeDisabled());
    expect(submitBtn).toHaveTextContent('Registering...');

    // Resolve pending
    // @ts-expect-error resolveFn defined above
    resolveFn({ user_id: 'u', api_key: 'k' });
    await flush();

    await waitFor(() => expect(submitBtn).not.toBeDisabled());
  });

  it('shows error when registerUser throws', async () => {
    mockRegisterUser.mockRejectedValueOnce(new Error('User exists'));

    setup();

    fireEvent.input(screen.getByLabelText('Username'), { target: { value: 'dup' } });
    fireEvent.input(screen.getByLabelText('Password'), { target: { value: 'pw' } });
    fireEvent.input(screen.getByLabelText('Confirm Password'), { target: { value: 'pw' } });

    const submitBtn = screen.getByRole('button', { name: 'Register' });
    fireEvent.submit(submitBtn);

    expect(await screen.findByText(/Registration failed: User exists/i)).toBeInTheDocument();
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('Back to Login button triggers onSwitchToLogin', async () => {
    const { onSwitchToLogin } = setup();
    const backBtn = screen.getByRole('button', { name: 'Back to Login' });
    fireEvent.click(backBtn);
    expect(onSwitchToLogin).toHaveBeenCalled();
  });

  it('backdrop click closes, inner click does not', async () => {
    const { onClose, container } = setup();

    const panel = container.querySelector('.max-w-md') as HTMLElement;
    fireEvent.click(panel);
    expect(onClose).not.toHaveBeenCalled();

    const backdrop = container.firstElementChild as HTMLElement;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });
});
