import { JSX } from 'preact/jsx-runtime';
import { useChat } from '../context/ChatContext.tsx';
import { Plus, X } from 'lucide-preact';
import { useRef } from "preact/hooks";

interface SidebarProps {
  hidden?: boolean;
  toggle?: () => void;
}

export default function Sidebar({
  hidden,
  toggle
}: SidebarProps): JSX.Element {
  const {
    conversationList,
    loadConversation,
    addConversation,
  } = useChat();
  const errorCount = useRef(0);

  const handleError: JSX.GenericEventHandler<HTMLImageElement> = (e) => {
    errorCount.current++;
    if (errorCount.current > 5) {
      console.error("Image failed to load after retries.");
      return;
    }
    if (e.target) {
      console.error(e)
      setTimeout(() => {
        (e.target as HTMLImageElement).src = `${(e.target as HTMLImageElement).src.split('?')[0]}?time=${Date.now()}`;
      }, 1000)
    } else {
      console.error("Image failed to load after retries.");
    }
  };

  return (
    <aside
      className={`transition-all duration-300 bg-white border-r border-gray-200 shadow-sm h-full flex flex-col ${hidden ? 'w-0 overflow-hidden' : 'w-40 p-2'}`}
    >
      <div className="flex items-center justify-between mb-4">
        <img
          src={window.location.protocol + "//" + window.location.hostname + ":8000/assets/logos/suhana_right.png"}
          alt="Suhana"
          className="h-6 w-auto opacity-90"
          onError={handleError}
        />
        <button
          onClick={toggle}
          className="text-gray-400 hover:text-black transition"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <h2 className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">
        Conversations
      </h2>

      <div className="flex-1 overflow-y-auto space-y-1 text-sm">
        <button
          onClick={() => addConversation()}
          className="w-full flex items-center gap-1 px-2 py-1 rounded hover:bg-neutral-100 text-gray-700 font-medium"
        >
          <Plus className="h-4 w-4" />
          New
        </button>

        {conversationList
          .slice()
          .reverse()
          .map(conv => (
            <button
              key={conv.id}
              onClick={() => loadConversation(conv.id)}
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
