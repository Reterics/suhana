import { useEffect, useState } from 'preact/hooks';

export function useFastAPI(baseUrl: string, apiKey: string) {
  const [apiReady, setApiReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const check = async () => {
      for (let i = 0; i < 5; i++) {
        const res = await fetch(`${baseUrl}/health`, {
          redirect: 'follow',
          headers: {
            ...(apiKey ? { 'x-api-key': apiKey } : {})
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

  const sendMessage = async (input: string, backend = 'ollama') => {
    const res = await fetch(`${baseUrl}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey ? { 'x-api-key': apiKey } : {})
      },
      body: JSON.stringify({ input, backend })
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
        ...(apiKey ? { 'x-api-key': apiKey } : {})
      },
      body: JSON.stringify({ input, backend })
    });

    const reader = res.body?.getReader();
    const decoder = new TextDecoder('utf-8');

    while (true) {
      const { value, done } = await reader!.read();
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
        ...(apiKey ? { 'x-api-key': apiKey } : {})
      },
      body: form
    });

    const data = await res.json();
    return data.text as string;
  };

  return {
    apiReady,
    error,
    sendMessage,
    sendStreamingMessage,
    transcribe
  };
}
