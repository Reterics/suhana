import { useState } from 'preact/hooks';
import { Login } from './Login';
import { Register } from './Register';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialView?: 'login' | 'register';
}

export function AuthModal({ isOpen, onClose, initialView = 'login' }: AuthModalProps) {
  const [currentView, setCurrentView] = useState<'login' | 'register'>(initialView);

  if (!isOpen) return null;

  return (
    <>
      {currentView === 'login' ? (
        <Login
          onClose={onClose}
          onSwitchToRegister={() => setCurrentView('register')}
        />
      ) : (
        <Register
          onClose={onClose}
          onSwitchToLogin={() => setCurrentView('login')}
        />
      )}
    </>
  );
}
