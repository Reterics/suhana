import { render } from 'preact';
import { ConversationProvider } from './context/ConversationContext';
import { App } from './components/App';
import './style.css';

render(<ConversationProvider><App /></ConversationProvider>, document.getElementById('app') as HTMLElement);
