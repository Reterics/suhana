import { useState } from 'preact/hooks';
import Sidebar from './Sidebar.tsx';
import { useChat } from '../context/ChatContext.tsx';
import { Menu } from 'lucide-preact';
import {ChatToolbar} from "./ChatToolbar.tsx";
import {ChatMessages} from "./ChatMessages.tsx";

export function App() {
  const {
    apiReady, error,
    conversationList, loadConversation,
    messages, setMessages,
    sendStreamingMessage
  } = useChat();

  const [sidebarOpen, setSidebarOpen] = useState(true);

  if (!apiReady) {
    return <div className="flex flex-col items-center justify-center h-screen text-gray-400 text-xl">
      <div className="flex flex-row items-center">
        <img src='./suhana.png' className="h-10 me-2" alt='Sohana logo'/> {error ? "Suhana failed" : "Suhana is starting..."}
      </div>
      <div className="text-base mt-2 max-w-1/2 text-wrap">{error && `Reason: ${error}`}</div>
    </div>;
  }

  async function handleSendMessage(input: string) {
    setMessages(prev => [...prev, {
      role: 'user',
      content: input
  }, {
      role: 'assistant',
      content: '...'
  }]);
    const index = messages.length + 1;
    let text = '';
    await sendStreamingMessage(input, token => {
      text += token;
      setMessages(prev => {
        const copy = [...prev];
        copy[index] = {
            role: 'assistant',
            content: text
        }
        return copy;
      });
    });
  }

  return (
    <div className="flex h-screen w-screen bg-neutral-50 text-gray-800">
      <Sidebar
        conversations={conversationList}
        onSelectConversation={loadConversation}
        hidden={!sidebarOpen}
        toggle={() => setSidebarOpen(!sidebarOpen)}
      />
      <main className="flex-1 flex flex-col h-full">
        <div className="flex items-center justify-between px-4 py-2 border-b border-b-gray-300 bg-white text-sm">
          <button onClick={() => setSidebarOpen(!sidebarOpen)}><Menu className="h-5 w-5 text-gray-500" /></button>
        </div>

        <ChatMessages messages={messages} />

        <ChatToolbar onSend={handleSendMessage} />
      </main>
    </div>
  );
}
