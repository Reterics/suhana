import {useEffect, useState} from 'preact/hooks';
import {useConversation} from "../context/ConversationContext.tsx";

export interface ConversationMeta {
  id: string;
  title: string;
  created: string;
  last_updated: string;
}


export function useFastAPI(baseUrl: string, apiKey: string) {
  const [apiReady, setApiReady] = useState(false);
  const { state, dispatch } = useConversation();
  const { conversationId } = state;
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const check = async () => {
      for (let i = 0; i < 5; i++) {
        const res = await fetch(`${baseUrl}/health`, {
          redirect: 'follow',
          headers: {
            ...(apiKey ? {'x-api-key': apiKey} : {})
          }
        }).catch(console.error)
        if (res?.ok) {
          setApiReady(true);
          return;
        } else if (res?.text) {
          const text = await res?.text().catch(console.error);
          if (text) {
            setError(`⚠️ Health check failed: ${text}`);
          }
        }
        await new Promise(res => setTimeout(res, 1000));
      }
      setError("⏱️ API did not become ready in time.");
    };
    void check();
  }, [baseUrl, apiKey]);

  const loadConversation = async (id: string) => {
    const res = await fetch(`${baseUrl}/conversations/${id}`, {
      headers: {
        ...(apiKey ? { 'x-api-key': apiKey } : {})
      }
    });
    const data = await res.json();
    dispatch({ type: 'SET_ID', payload: id });
    dispatch({ type: 'SET_HISTORY', payload: data.history || [] });
  };

  const listConversations = async (): Promise<ConversationMeta[]> => {
    const res = await fetch(`${baseUrl}/conversations`, {
      headers: {
        ...(apiKey ? { 'x-api-key': apiKey } : {})
      }
    });
    return await res.json();
  };

  const sendMessage = async (input: string, backend = 'ollama') => {
    const res = await fetch(`${baseUrl}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? {'x-api-key': apiKey} : {})
      },
      body: JSON.stringify({input, backend, conversation_id: conversationId})
    });
    const data = await res.json();
    return data.response as string;
  };

  const sendStreamingMessage = async (
    input: string,
    onToken: (token: string) => void,
    backend = 'ollama'
  ) => {
    const res = await fetch(`${baseUrl}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? {'x-api-key': apiKey} : {})
      },
      body: JSON.stringify({input, backend, conversation_id: conversationId})
    });

    const reader = res.body?.getReader();
    const decoder = new TextDecoder('utf-8');

    while (true) {
      const {value, done} = await reader!.read();
      if (done) break;
      if (value) onToken(decoder.decode(value));
    }
  };

  const transcribe = async (blob: Blob): Promise<string> => {
    const form = new FormData();
    form.append('audio', blob, 'speech.webm');

    const res = await fetch(`${baseUrl}/transcribe`, {
      method: 'POST',
      headers: {
        ...(apiKey ? {'x-api-key': apiKey} : {})
      },
      body: form
    });

    const data = await res.json();
    return data.text as string;
  };

  return {
    apiReady,
    error,
    conversationId,
    history: state.history,
    dispatch,
    listConversations,
    loadConversation,
    sendMessage,
    sendStreamingMessage,
    transcribe
  };
}
