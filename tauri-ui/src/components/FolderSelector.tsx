import { useEffect, useState } from 'preact/hooks';
import { BASE_URL } from '../context/ChatContext.tsx';
import { ChevronUp, ChevronLeft, ChevronRight } from 'lucide-preact';

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

export function FolderSelector({
  onSelect
}: {
  onSelect: (path: string) => void;
}) {
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
      const res = await fetch(
        `${BASE_URL}/browse-folders?path=${encodeURIComponent(path)}`
      );

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Failed to fetch folders');
      }

      const data: BrowseFoldersResponse = await res.json();
      setCurrentPath(data.current);
      setInputPath(data.current);
      setSeparator(data.separator);
      setFolders(data.subfolders);
      setPathParts(data.path_parts);
      setRecentProjects(data.recent_projects || []);
      setShowRecents(data.subfolders.length === 0 || path === '');

      // Update navigation history
      if (updateHistory) {
        // If we're not at the end of history, remove forward history
        if (historyPosition < history.length - 1) {
          setHistory(prev => prev.slice(0, historyPosition + 1));
        }
        // Add current path to history
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
    <div className="flex flex-col gap-3 max-h-[70vh] overflow-hidden">
      <div className="flex justify-between items-center border-b border-neutral-200 pb-2">
        <h3 className="font-medium text-lg text-neutral-800">Select Project Folder</h3>
        {isLoading && (
          <div className="text-sm text-neutral-500">Loading...</div>
        )}
      </div>

      <div className="flex gap-2 bg-gray-100 p-2 rounded-md border border-gray-200">
        <div className="flex gap-1">
          <button
            onClick={goBack}
            disabled={historyPosition <= 0}
            className="text-sm px-2 py-2 bg-white border border-neutral-300 rounded-md hover:bg-neutral-100 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            title="Go back"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            onClick={goForward}
            disabled={historyPosition >= history.length - 1}
            className="text-sm px-2 py-2 bg-white border border-neutral-300 rounded-md hover:bg-neutral-100 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            title="Go forward"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            onClick={goUp}
            disabled={pathParts.length <= 1}
            className="text-sm px-2 py-2 bg-white border border-neutral-300 rounded-md hover:bg-neutral-100 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
            title="Go to parent directory"
          >
            <ChevronUp className="h-4 w-4" />
          </button>
        </div>
        <input
          type="text"
          className="flex-1 border border-neutral-300 px-3 py-2 rounded-md text-sm bg-white focus:ring-2 focus:ring-blue-400 focus:border-blue-400 focus:outline-none"
          value={inputPath}
          placeholder="Enter path directly..."
          onInput={e => setInputPath((e.target as HTMLInputElement).value)}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              void fetchFolders(inputPath);
            }
          }}
        />
      </div>

      <div className="flex items-center gap-1 text-sm bg-gray-50 p-2 rounded overflow-x-auto whitespace-nowrap truncate">
        {pathParts.map((part, index) => (
          <div key={part.path} className="flex items-center h-12 whitespace-nowrap flex-nowrap text-nowrap">
            {index > 0 && <span className="mx-1 text-gray-400">/</span>}
            <button
              onClick={() => fetchFolders(part.path)}
              className="hover:underline hover:text-blue-600 truncate max-w-[150px]"
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

      <div className="flex-1 overflow-y-auto min-h-[200px] max-h-[300px] border rounded p-1">
        {showRecents && recentProjects.length > 0 && (
          <div className="mb-3">
            <h4 className="font-medium text-sm text-gray-700 mb-2 px-2">Recent Projects</h4>
            <div className="flex flex-col gap-1">
              {recentProjects.map(project => (
                <button
                  key={project}
                  onClick={() => fetchFolders(project)}
                  onDblClick={() => onSelect(project)}
                  className="flex items-center gap-2 p-2 text-left hover:bg-blue-50 rounded group"
                  title={`${project} (Double-click to select)`}
                >
                  <span className="text-blue-600">📂</span>
                  <span className="flex-1 truncate text-sm">{project.split(separator).pop()}</span>
                  <span className="text-xs text-gray-500 group-hover:text-blue-600">Open</span>
                </button>
              ))}
            </div>
            <div className="border-t my-2"></div>
          </div>
        )}

        <div className="grid grid-cols-1 gap-1">
          {folders.length === 0 && !isLoading ? (
            <div className="text-center text-gray-500 py-8">
              No folders found in this directory
            </div>
          ) : (
            folders.map(folder => (
              <button
                key={folder.path}
                onClick={() => fetchFolders(folder.path)}
                onDblClick={() => onSelect(folder.path)}
                className={`flex items-center gap-2 p-2 text-left hover:bg-blue-50 rounded ${
                  folder.is_project ? 'bg-blue-50' : ''
                }`}
                title={`${folder.path} (Double-click to select)`}
              >
                <span className={folder.is_project ? 'text-blue-600' : 'text-gray-600'}>
                  {folder.is_project ? '📁' : '📂'}
                </span>
                <span className="flex-1 truncate text-sm">{folder.name}</span>
                {folder.is_project && (
                  <span className="text-xs bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded">
                    Project
                  </span>
                )}
                {folder.modified > 0 && (
                  <span className="text-xs text-gray-500">
                    {formatDate(folder.modified)}
                  </span>
                )}
              </button>
            ))
          )}
        </div>
      </div>

      <div className="flex justify-between pt-2 border-t">
        <button
          onClick={() => onSelect('')}
          className="text-sm px-3 py-2 rounded text-gray-700 hover:bg-gray-100"
        >
          Cancel
        </button>
        <div className="flex gap-2">
          <button
            onClick={() => setShowRecents(!showRecents)}
            className="text-sm px-3 py-2 rounded text-gray-700 hover:bg-gray-100"
            title={showRecents ? 'Hide recent projects' : 'Show recent projects'}
          >
            {showRecents ? 'Hide Recents' : 'Show Recents'}
          </button>
          <button
            onClick={() => onSelect(currentPath)}
            className="text-sm px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 focus:ring-2 focus:ring-blue-300 focus:outline-none"
          >
            Select This Folder
          </button>
        </div>
      </div>
    </div>
  );
}
