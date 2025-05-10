import { JSX } from 'preact/jsx-runtime';
import { ConversationMeta } from '../context/ChatContext';

interface SidebarProps {
  conversations: ConversationMeta[];
  onSelectConversation?: (id: string) => void;
}

export default function Sidebar({ conversations, onSelectConversation }: SidebarProps): JSX.Element {
  return (
    <aside className="w-52 border-r border-gray-200 flex flex-col p-4 bg-gray-50">
      <img
        src="http://localhost:8000/assets/logos/suhana_right.png"
        alt="Suhana Logo"
        className="h-14 mb-6 w-fit"
      />
      <h2 className="text-lg font-semibold mb-2">Conversations</h2>
      <div className="flex-1 overflow-y-auto space-y-2">
        <button
            key={'create_new'}
            onClick={() => onSelectConversation?.('id' + Date.now())}
            className="w-full text-left p-2 rounded hover:bg-gray-200"
          >
            New
          </button>
        {conversations.reverse().map((conv) => (
          <button
            key={conv.id}
            onClick={() => onSelectConversation?.(conv.id)}
            className="w-full text-left p-2 rounded hover:bg-gray-200"
          >
            {conv.title || conv.id.slice(0, 8)}
          </button>
        ))}
      </div>
      <div className="mt-4 text-xs text-gray-400">v0.1 • Light UI</div>
    </aside>
  );
}
