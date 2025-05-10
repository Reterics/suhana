import { render } from 'preact';
import { App } from './components/App';
import {ChatProvider} from "./context/ChatContext.tsx";
import './style.css';

render(<ChatProvider><App /></ChatProvider>, document.getElementById('app') as HTMLElement);
