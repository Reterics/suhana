import { JSX } from 'preact/jsx-runtime';
import { useEffect, useRef } from 'preact/hooks';
import {ChatMessage} from "../context/ChatContext.tsx";
import {CodeBlock} from "./CodeBlock.tsx";

interface Props {
  messages: ChatMessage[];
}

function parseContent(content: string): JSX.Element[] {
  const parts: JSX.Element[] = [];
  const regex = /```(\w+)?\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(content)) !== null) {
    const [_full, lang = '', code] = match;
    const index = match.index;

    if (index > lastIndex) {
      parts.push(<p>{content.slice(lastIndex, index)}</p>);
    }

    parts.push(<CodeBlock code={code.trim()} lang={lang}></CodeBlock>);

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < content.length) {
    parts.push(<p>{content.slice(lastIndex)}</p>);
  }

  return parts;
}

export function ChatMessages({ messages }: Props) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'instant' });
  }, [messages]);

  return (
    <div className="flex-1 flex-col overflow-y-auto px-4 py-3 space-y-2 text-sm">
      {messages.map((m, i) => (
        <div key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
          <div className={`inline-block max-w-full px-3 py-2 rounded shadow-sm whitespace-pre-wrap ${
            m.role === 'user'
              ? 'bg-zinc-700 text-white'
              : 'bg-neutral-200 text-zinc-900'
          }`}>
            {parseContent(m.content)}
          </div>
        </div>
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
}
