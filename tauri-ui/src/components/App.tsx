import { useEffect, useState } from 'preact/hooks';
import Sidebar from './Sidebar.tsx';
import { BASE_URL, useChat } from '../context/ChatContext.tsx';
import { Menu, FolderSearch, Package, ChevronLeft } from 'lucide-preact';
import { ChatToolbar } from './ChatToolbar.tsx';
import { ChatMessages } from './ChatMessages.tsx';
import { FolderSelector } from './FolderSelector.tsx';
import { ProjectMetadata } from './ProjectMetadata.tsx';

export function App() {
  const {
    apiReady,
    error,
    conversationList,
    loadConversation,
    conversationId,
    apiKey,
    messages,
    setMessages,
    sendStreamingMessage,
    projectMetadata,
    setProjectMetadata
  } = useChat();

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(false);
  const [currentMode, setCurrentMode] = useState<'normal' | 'development'>(
    'normal'
  );
  const [projectPath, setProjectPath] = useState<string>('');
  const [folderSelectorOpen, setFolderSelectorOpen] = useState(false);

  if (!apiReady) {
    return (
      <div className="flex flex-col items-center justify-center h-screen text-gray-400 text-xl">
        <div className="flex flex-row items-center">
          <img src="./suhana.png" className="h-10 me-2" alt="Sohana logo" />{' '}
          {error ? 'Suhana failed' : 'Suhana is starting...'}
        </div>
        <div className="text-base mt-2 max-w-1/2 text-wrap">
          {error && `Reason: ${error}`}
        </div>
      </div>
    );
  }

  async function handleSendMessage(input: string) {
    setMessages(prev => [
      ...prev,
      {
        role: 'user',
        content: input
      },
      {
        role: 'assistant',
        content: '...'
      }
    ]);
    const index = messages.length + 1;
    let text = '';
    await sendStreamingMessage(input, token => {
      text += token;
      setMessages(prev => {
        const copy = [...prev];
        copy[index] = {
          role: 'assistant',
          content: text
        };
        return copy;
      });
    });
  }

  async function updateConversationMetadata(mode: string, path: string) {
    const response = await fetch(
      `${BASE_URL}/conversations/${conversationId}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { 'x-api-key': apiKey } : {})
        },
        body: JSON.stringify({
          input: 'Update mode/project path',
          backend: 'ollama',
          conversation_id: conversationId,
          mode,
          project_path: path
        })
      }
    ).then(response => response.json());
    if (response?.project_path) {
      setProjectPath(response.project_path);
    }
    if (response?.mode) {
      setCurrentMode(response.mode);
    }
    if (response?.project_metadata) {
      setProjectMetadata(response.project_metadata);
      // Automatically open the right sidebar when project metadata is available
      setRightSidebarOpen(true);
    }
  }

  useEffect(() => {
    if (conversationId) {
      void updateConversationMetadata(currentMode, projectPath);
    }
  }, [currentMode]);

  //
  return (
    <div className="flex h-screen w-screen bg-neutral-50 text-gray-800">
      <Sidebar
        conversations={conversationList}
        onSelectConversation={loadConversation}
        hidden={!sidebarOpen}
        toggle={() => setSidebarOpen(!sidebarOpen)}
      />
      <main className="flex-1 flex flex-col h-full">
        <div className="flex items-center flex-wrap justify-between gap-1 px-4 py-2 border-b bg-white shadow-sm text-sm">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-gray-500 hover:text-black transition"
            title="Toggle Sidebar"
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="flex gap-2 flex-wrap">
            <div className="flex items-center gap-2">
              <label htmlFor="modeSelect" className="text-gray-600 font-medium">
                Mode
              </label>
              <select
                id="modeSelect"
                className="border border-gray-300 rounded-md px-2 py-1 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={currentMode}
                onChange={e =>
                  setCurrentMode(
                    e.currentTarget.value as 'normal' | 'development'
                  )
                }
              >
                <option value="normal">Normal</option>
                <option value="development">Development</option>
              </select>
            </div>

            <div className="flex items-center gap-3 flex-1 max-w-md">
              <span className="text-sm font-medium text-neutral-700">
                Project:
              </span>

              {projectPath && (
                <span className="text-sm text-neutral-600 truncate max-w-[200px]">
                  {projectPath.split('/').pop()}
                </span>
              )}
              <button
                onClick={() => setFolderSelectorOpen(true)}
                className="flex items-center gap-2 px-3 py-1 text-sm rounded-md border border-neutral-300 bg-neutral-100 hover:bg-neutral-200 transition"
              >
                <FolderSearch className="h-4 w-4 text-neutral-600" />
              </button>
            </div>

            {projectMetadata && (
              <button
                onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
                className="flex items-center gap-2 px-3 py-1 text-sm rounded-md border border-neutral-300 bg-neutral-100 hover:bg-neutral-200 transition"
                title="Toggle Project Metadata"
              >
                <Package className="h-4 w-4 text-blue-500" />
                <span className="text-sm font-medium">
                  {projectMetadata.name || projectMetadata.project_type || 'Project Info'}
                </span>
              </button>
            )}
          </div>
        </div>

        <ChatMessages messages={messages} />

        <ChatToolbar onSend={handleSendMessage} />
      </main>

      <aside
        className={`transition-all duration-300 bg-white border-l border-gray-200 shadow-sm h-full flex flex-col ${
          rightSidebarOpen ? 'w-64 p-2' : 'w-0 overflow-hidden'
        }`}
      >
        {projectMetadata && (
          <>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Package className="h-5 w-5 text-blue-500" />
                <h2 className="text-sm font-semibold text-gray-700">
                  Project Metadata
                </h2>
              </div>
              <button
                onClick={() => setRightSidebarOpen(false)}
                className="text-gray-400 hover:text-black transition"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <ProjectMetadata metadata={projectMetadata} />
            </div>
          </>
        )}
      </aside>

      {folderSelectorOpen && (
        <FolderSelector
              onSelect={path => {
                setFolderSelectorOpen(false);
                if (conversationId) {
                  void updateConversationMetadata(currentMode, path);
                }
              }}
              onClose={() => setFolderSelectorOpen(false)}
            />
      )}
    </div>
  );
}
