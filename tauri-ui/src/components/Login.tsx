import { useState } from 'preact/hooks';
import { useChat } from '../context/ChatContext';
import { X } from 'lucide-preact';

interface LoginProps {
  onClose: () => void;
  onSwitchToRegister: () => void;
}

export function Login({ onClose, onSwitchToRegister }: LoginProps) {
  const { setApiKey, setCurrentUser } = useChat();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: Event) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8000/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      if (!response.ok)
        throw new Error((await response.text()) || 'Login failed');
      const data = await response.json();
      setApiKey(data.api_key);
      setCurrentUser(data.user_id);
      onClose();
    } catch (err) {
      setError(`Login failed: ${(err as Error).message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/40 z-40 flex items-center justify-center"
      onClick={onClose}
    >
      <div
        className="w-[90%] max-w-md relative z-50 bg-white border border-gray-200 rounded-md shadow-md p-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between pb-2 border-b border-gray-100 mb-4">
          <h3 className="text-lg font-semibold text-gray-800">Login</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-black hover:bg-gray-100 p-2 rounded"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="bg-red-50 text-red-700 p-3 rounded border border-red-200 text-sm mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="flex flex-col gap-4">
          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              value={username}
              onInput={e => setUsername((e.target as HTMLInputElement).value)}
              required
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              value={password}
              onInput={e => setPassword((e.target as HTMLInputElement).value)}
              required
            />
          </div>

          <div className="flex justify-between items-center pt-2 border-t border-gray-100">
            <button
              type="button"
              className="text-sm text-gray-600 hover:text-black"
              onClick={onSwitchToRegister}
            >
              Register
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="text-sm px-4 py-2 rounded bg-black text-white hover:bg-gray-900 shadow-sm disabled:opacity-50"
            >
              {isLoading ? 'Logging in...' : 'Login'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
