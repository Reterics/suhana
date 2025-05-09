import { JSX } from 'preact/jsx-runtime';

interface SidebarProps {
  onSelectConversation?: (id: string) => void;
}

export default function Sidebar({ onSelectConversation }: SidebarProps): JSX.Element {
  const conversations = ['Welcome', 'Voice Test']; // Placeholder

  return (
    <aside className="w-52 border-r border-gray-200 flex flex-col p-4 bg-gray-50">
      <img src="http://localhost:8000/assets/logos/suhana_right.png" alt="Suhana Logo" className="h-14 mb-6 w-fit" />
      <h2 className="text-lg font-semibold mb-2">Conversations</h2>
      <div className="flex-1 overflow-y-auto space-y-2">
        {conversations.map((title, i) => (
          <button
            key={i}
            onClick={() => onSelectConversation?.(title)}
            className="w-full text-left p-2 rounded hover:bg-gray-200"
          >
            {title}
          </button>
        ))}
      </div>
      <div className="mt-4 text-xs text-gray-400">
        v0.1 • Light UI
      </div>
    </aside>
  );
}
