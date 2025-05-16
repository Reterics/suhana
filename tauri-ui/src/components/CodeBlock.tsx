import { highlightCode } from '../utils/highlightCode.ts';
import './CodeBlock.css';

interface Props {
  code: string;
  lang: string;
}

export function CodeBlock({ code, lang }: Props) {
  function copyToClipboard() {
    void navigator.clipboard.writeText(code);
  }

  return (
    <div className="code-block-container relative mt-1 rounded overflow-hidden bg-neutral-100 text-zinc-700 border border-zinc-300">
      <div className="code-toolbar flex justify-between text-xs px-3 py-1 bg-zinc-800 text-zinc-300 font-mono">
        <span className="language-label capitalize">
          {lang || 'Unknown Language'}
        </span>
        <button
          className="copy-btn text-zinc-400 hover:text-white"
          onClick={copyToClipboard}
        >
          📋 Copy
        </button>
      </div>
      <pre className="overflow-x-auto m-0">
        <code
          className={`language-${lang} whitespace-pre`}
          dangerouslySetInnerHTML={{ __html: highlightCode(lang, code.trim()) }}
        />
      </pre>
    </div>
  );
}
