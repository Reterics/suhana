import { useEffect, useState } from 'preact/hooks';
import { BASE_URL } from '../context/ChatContext.tsx';

export function FolderSelector({
  onSelect
}: {
  onSelect: (path: string) => void;
}) {
  const [currentPath, setCurrentPath] = useState('');
  const [folders, setFolders] = useState<string[]>([]);
  const [inputPath, setInputPath] = useState('');
  const [separator, setSeparator] = useState('/');

  async function fetchFolders(path = '') {
    const res = await fetch(
      `${BASE_URL}/browse-folders?path=${encodeURIComponent(path)}`
    );
    const data = await res.json();
    setCurrentPath(data.current);
    setInputPath(data.current);
    setSeparator(data.separator);
    setFolders(data.subfolders);
  }

  useEffect(() => {
    void fetchFolders();
  }, []);

  function goUp() {
    const parts = currentPath.split(separator);
    if (parts.length > 1) {
      parts.pop();
      const parent = parts.join(separator) || separator;
      void fetchFolders(parent);
    }
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <input
          type="text"
          className="w-full border px-3 py-1 rounded text-sm"
          value={inputPath}
          onInput={e => setInputPath((e.target as HTMLInputElement).value)}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              void fetchFolders(inputPath);
            }
          }}
        />
        <button
          onClick={goUp}
          className="text-sm px-2 py-1 bg-gray-100 border rounded hover:bg-gray-200"
        >
          ↑ Up
        </button>
      </div>
      <div className="flex gap-2 flex-wrap">
        {folders.map(folder => (
          <button
            key={folder}
            onClick={() => fetchFolders(`${currentPath}/${folder}`)}
            className="text-sm border px-2 py-1 rounded hover:bg-gray-100"
          >
            {folder}
          </button>
        ))}
      </div>
      <div>
        <button
          onClick={() => onSelect(currentPath)}
          className="mt-2 text-sm px-3 py-1 rounded bg-black text-white hover:bg-gray-800"
        >
          Select This Folder
        </button>
      </div>
    </div>
  );
}
