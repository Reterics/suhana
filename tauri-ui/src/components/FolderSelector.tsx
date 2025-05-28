import {useEffect, useState} from 'preact/hooks';
import {BASE_URL} from '../context/ChatContext.tsx';
import {ChevronUp, ChevronLeft, ChevronRight, X} from 'lucide-preact';

interface PathPart {
  name: string;
  path: string;
}

interface FolderInfo {
  name: string;
  path: string;
  is_project: boolean;
  modified: number;
}

interface BrowseFoldersResponse {
  current: string;
  parent: string | null;
  path_parts: PathPart[];
  subfolders: FolderInfo[];
  separator: string;
  recent_projects: string[];
}

export function FolderSelector({onSelect, onClose}: { onSelect: (path: string) => void, onClose: () => void }) {
  const [currentPath, setCurrentPath] = useState('');
  const [folders, setFolders] = useState<FolderInfo[]>([]);
  const [pathParts, setPathParts] = useState<PathPart[]>([]);
  const [recentProjects, setRecentProjects] = useState<string[]>([]);
  const [inputPath, setInputPath] = useState('');
  const [separator, setSeparator] = useState('/');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRecents, setShowRecents] = useState(true);
  const [history, setHistory] = useState<string[]>([]);
  const [historyPosition, setHistoryPosition] = useState(-1);

  async function fetchFolders(path = '', updateHistory = true) {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BASE_URL}/browse-folders?path=${encodeURIComponent(path)}`);
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed to fetch folders');
      const data: BrowseFoldersResponse = await res.json();
      setCurrentPath(data.current);
      setInputPath(data.current);
      setSeparator(data.separator);
      setFolders(data.subfolders);
      setPathParts(data.path_parts);
      setRecentProjects(data.recent_projects || []);
      setShowRecents(data.subfolders.length === 0 || path === '');
      if (updateHistory) {
        if (historyPosition < history.length - 1) setHistory(prev => prev.slice(0, historyPosition + 1));
        setHistory(prev => [...prev, data.current]);
        setHistoryPosition(prev => prev + 1);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  }

  function goBack() {
    if (historyPosition > 0) {
      const newPosition = historyPosition - 1;
      setHistoryPosition(newPosition);
      void fetchFolders(history[newPosition], false);
    }
  }

  function goForward() {
    if (historyPosition < history.length - 1) {
      const newPosition = historyPosition + 1;
      setHistoryPosition(newPosition);
      void fetchFolders(history[newPosition], false);
    }
  }

  useEffect(() => {
    void fetchFolders();
  }, []);

  function goUp() {
    if (pathParts.length > 1) {
      const parentPart = pathParts[pathParts.length - 2];
      void fetchFolders(parentPart.path);
    }
  }

  function formatDate(timestamp: number): string {
    if (!timestamp) return '';
    return new Date(timestamp * 1000).toLocaleDateString();
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-40 flex items-center justify-center"
         onClick={onClose}
    >
      <div
        className="w-[90%] max-w-xl relative z-50 bg-white border border-gray-200 rounded-md shadow-md p-4 pt-2"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-2 pb-2 border-b border-gray-100">
          <h3 className="font-semibold text-lg text-gray-800">
            Select Project Folder {isLoading && <span className="text-sm text-gray-400">Loading...</span>}
          </h3>
          <button
            onClick={onClose}
            className="cursor-pointer text-gray-400 hover:text-black hover:bg-gray-100 rounded-md p-2 focus:outline-none transition"
            title="Close"
            aria-label="Close"
          >
              <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex flex-col gap-4">
          <div className="flex gap-2 bg-gray-50 p-2 rounded border border-gray-200">
            <div className="flex gap-1">
              <button onClick={goBack} disabled={historyPosition <= 0}
                      className="px-2 py-2 border border-gray-200 rounded hover:bg-gray-100 disabled:opacity-50"
                      title="Go back"><ChevronLeft className="h-4 w-4"/></button>
              <button onClick={goForward} disabled={historyPosition >= history.length - 1}
                      className="px-2 py-2 border border-gray-200 rounded hover:bg-gray-100 disabled:opacity-50"
                      title="Go forward"><ChevronRight className="h-4 w-4"/></button>
              <button onClick={goUp} disabled={pathParts.length <= 1}
                      className="px-2 py-2 border border-gray-200 rounded hover:bg-gray-100 disabled:opacity-50"
                      title="Go to parent directory"><ChevronUp className="h-4 w-4"/></button>
            </div>
            <input
              type="text"
              className="flex-1 border border-gray-200 px-3 py-2 rounded text-sm bg-white focus:ring-2 focus:ring-black focus:border-black focus:outline-none"
              value={inputPath}
              placeholder="Enter path directly..."
              onInput={e => setInputPath((e.target as HTMLInputElement).value)}
              onKeyDown={e => {
                if (e.key === 'Enter') void fetchFolders(inputPath);
              }}
            />
          </div>

          <div
            className="flex items-center gap-1 text-sm bg-gray-50 p-2 rounded overflow-x-auto whitespace-nowrap truncate border border-gray-100">
            {pathParts.map((part, index) => (
              <div key={part.path} className="flex items-center whitespace-nowrap">
                {index > 0 && <span className="mx-1 text-gray-300">/</span>}
                <button
                  onClick={() => fetchFolders(part.path)}
                  className="hover:underline hover:text-black truncate max-w-[140px] text-gray-700"
                  title={part.path}
                >
                  {part.name || (index === 0 ? 'Root' : '/')}
                </button>
              </div>
            ))}
          </div>

          {error && (
            <div className="bg-red-50 text-red-700 p-3 rounded border border-red-200 text-sm">
              {error}
            </div>
          )}

          <div
            className="flex-1 overflow-y-auto min-h-[200px] max-h-[300px] border border-gray-100 rounded p-2 bg-gray-50">
            {showRecents && recentProjects.length > 0 && (
              <div className="mb-2">
                <h4 className="font-medium text-sm text-gray-600 mb-2 px-2">Recent Projects</h4>
                <div className="flex flex-col gap-1">
                  {recentProjects.map(project => (
                    <button
                      key={project}
                      onClick={() => fetchFolders(project)}
                      onDblClick={() => onSelect(project)}
                      className="flex items-center gap-2 p-2 text-left hover:bg-gray-200 rounded group"
                      title={`${project} (Double-click to select)`}
                    >
                      <span className="text-black">📂</span>
                      <span className="flex-1 truncate text-sm">{project.split(separator).pop()}</span>
                      <span className="text-xs text-gray-400 group-hover:text-black">Open</span>
                    </button>
                  ))}
                </div>
                <div className="border-t my-2 border-gray-200"></div>
              </div>
            )}

            <div className="grid grid-cols-1 gap-1">
              {folders.length === 0 && !isLoading ? (
                <div className="text-center text-gray-400 py-8">
                  No folders found in this directory
                </div>
              ) : (
                folders.map(folder => (
                  <button
                    key={folder.path}
                    onClick={() => fetchFolders(folder.path)}
                    onDblClick={() => onSelect(folder.path)}
                    className={`flex items-center gap-2 p-2 text-left hover:bg-gray-200 rounded border border-transparent ${
                      folder.is_project ? 'bg-black/5 border-black/10' : ''
                    }`}
                    title={`${folder.path} (Double-click to select)`}
                  >
                <span className={folder.is_project ? 'text-black' : 'text-gray-600'}>
                  {folder.is_project ? '📁' : '📂'}
                </span>
                    <span className="flex-1 truncate text-sm">{folder.name}</span>
                    {folder.is_project && (
                      <span className="text-xs bg-black/10 text-black px-2 py-0.5 rounded font-medium">
                    Project
                  </span>
                    )}
                    {folder.modified > 0 && (
                      <span className="text-xs text-gray-400">{formatDate(folder.modified)}</span>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="flex justify-between pt-4 border-t border-gray-100 mt-2">
            <button
              onClick={() => onSelect('')}
              className="text-sm px-4 py-2 rounded border border-gray-200 text-gray-700 hover:bg-gray-100"
            >Cancel
            </button>
            <div className="flex gap-2">
              <button
                onClick={() => setShowRecents(!showRecents)}
                className="text-sm px-3 py-2 rounded border border-gray-200 text-gray-700 hover:bg-gray-100"
                title={showRecents ? 'Hide recent projects' : 'Show recent projects'}
              >{showRecents ? 'Hide Recents' : 'Show Recents'}</button>
              <button
                onClick={() => onSelect(currentPath)}
                className="text-sm px-4 py-2 rounded bg-black text-white hover:bg-gray-900 shadow-sm"
              >Select This Folder
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
