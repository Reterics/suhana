import { JSX } from 'preact/jsx-runtime';
import {ConversationMeta} from "../context/ChatContext.tsx";
import { Plus, X } from 'lucide-preact';

interface SidebarProps {
  conversations: ConversationMeta[];
  onSelectConversation?: (id: string) => void;
  hidden?: boolean;
  toggle?: () => void;
}

export default function Sidebar({ conversations, onSelectConversation, hidden, toggle }: SidebarProps): JSX.Element {
  return (
    <aside className={`transition-all duration-300 bg-white border-r border-gray-200 shadow-sm h-full flex flex-col ${hidden ? 'w-0 overflow-hidden' : 'w-40 p-2'}`}>
      <div className="flex items-center justify-between mb-4">
        <img
          src="http://localhost:8000/assets/logos/suhana_right.png"
          alt="Suhana"
          className="h-6 w-auto opacity-90"
        />
        <button onClick={toggle} className="text-gray-400 hover:text-black transition">
          <X className="h-4 w-4" />
        </button>
      </div>

      <h2 className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">Conversations</h2>

      <div className="flex-1 overflow-y-auto space-y-1 text-sm">
        <button
          onClick={() => onSelectConversation?.('id' + Date.now())}
          className="w-full flex items-center gap-1 px-2 py-1 rounded hover:bg-neutral-100 text-gray-700 font-medium"
        >
          <Plus className="h-4 w-4" />
          New
        </button>

        {conversations.slice().reverse().map((conv) => (
          <button
            key={conv.id}
            onClick={() => onSelectConversation?.(conv.id)}
            className="w-full text-left px-2 py-1 rounded hover:bg-neutral-100 text-gray-700 truncate"
            title={conv.title || conv.id}
          >
            {conv.title || conv.id.slice(0, 8)}
          </button>
        ))}
      </div>

      <div className="text-[10px] text-gray-300 pt-4 pb-2 border-t mt-4">
        v0.1 • Suhana
      </div>
    </aside>
  );
}
