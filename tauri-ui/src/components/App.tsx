import { useEffect, useRef, useState } from 'preact/hooks';
import Sidebar from './Sidebar.tsx';
import {useChat} from "../context/ChatContext.tsx";

export function App() {
  const {
    apiKey,
    setApiKey,
    apiReady,
    error,
    conversationList,
    loadConversation,
    messages,
    setMessages,
    sendStreamingMessage,
    transcribe
  } = useChat();

  const [input, setInput] = useState('');
  const [volume, setVolume] = useState(0);
  const [micDeviceId, setMicDeviceId] = useState<string>('');
  const [micDevices, setMicDevices] = useState<MediaDeviceInfo[]>([]);
  const [micTestStatus, setMicTestStatus] = useState<'pending' | 'success' | 'fail' | null>(null);
  const intervalRef = useRef<number>();

  useEffect(() => {
    navigator.mediaDevices.enumerateDevices().then(devices => {
      const mics = devices.filter(d => d.kind === 'audioinput');
      setMicDevices(mics);
    });
  }, []);

  if (!apiReady) {
    return <div className="flex flex-col items-center justify-center h-screen text-gray-400 text-xl">
      <div className="flex flex-row items-center">
        <img src='./suhana.png' className="h-10 me-2" alt='Sohana logo'/> {error ? "Suhana failed" : "Suhana is starting..."}
      </div>
      <div className="text-base mt-2 max-w-1/2 text-wrap">{error && `Reason: ${error}`}</div>
    </div>;
  }

  async function testMic(deviceId: string) {
    setMicTestStatus('pending');
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: { exact: deviceId } } });
    const context = new AudioContext();
    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    const data = new Uint8Array(analyser.fftSize);
    source.connect(analyser);
    let maxVolume = 0;

    intervalRef.current = window.setInterval(() => {
      analyser.getByteTimeDomainData(data);
      const avg = data.reduce((sum, val) => sum + Math.abs(val - 128), 0) / data.length;
      setVolume(avg);
      if (avg > maxVolume) maxVolume = avg;
    }, 200);

    setTimeout(() => {
      clearInterval(intervalRef.current);
      setVolume(0);
      stream.getTracks().forEach(track => track.stop());
      setMicTestStatus(maxVolume > 5 ? 'success' : 'fail');
    }, 5000);
  }

  async function handleSendMessage() {
    if (!input.trim()) return;
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
    setInput('');
  }

  async function startRecording() {
    const constraints = micDeviceId ? { deviceId: { exact: micDeviceId } } : true;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: constraints });
    const context = new AudioContext();
    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    const data = new Uint8Array(analyser.fftSize);
    source.connect(analyser);
    const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    const chunks: Blob[] = [];

    recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
    recorder.onstop = async () => {
      clearInterval(intervalRef.current);
      setVolume(0);
      stream.getTracks().forEach(track => track.stop());
      const blob = new Blob(chunks, { type: 'audio/webm' });
      const text = await transcribe(blob);
      setInput(text);
    };

    recorder.start();
    let silenceStart: number | null = null;
    const silenceThreshold = 3;
    const volumeThreshold = 5;

    intervalRef.current = window.setInterval(() => {
      analyser.getByteTimeDomainData(data);
      const avg = data.reduce((sum, val) => sum + Math.abs(val - 128), 0) / data.length;
      setVolume(avg);
      const now = Date.now();
      if (avg < volumeThreshold) {
        if (silenceStart === null) silenceStart = now;
        else if (now - silenceStart > silenceThreshold * 1000) recorder.stop();
      } else {
        silenceStart = null;
      }
    }, 200);
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden text-gray-800 bg-white">
      <Sidebar
        conversations={conversationList}
        onSelectConversation={loadConversation}
      />
      <main className="flex-1 flex flex-col p-6 overflow-hidden">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium mb-1">Select Microphone</label>
            <select
              className="w-full border rounded p-2 text-sm"
              value={micDeviceId}
              onChange={e => {
                const id = e.currentTarget.value;
                setMicDeviceId(id);
                if (id) void testMic(id);
              }}
            >
              <option value="">(Default)</option>
              {micDevices.map((d, i) => (
                <option key={i} value={d.deviceId}>{d.label || `Mic ${i}`}</option>
              ))}
            </select>
            {micTestStatus && (
              <div className="mt-1 text-sm">
                Mic Test: {micTestStatus === 'success' ? '✅ Working' : micTestStatus === 'fail' ? '❌ No input' : '⏳ Testing...'}
              </div>
            )}
            <div className="w-full h-2 bg-gray-200 mt-2 rounded overflow-hidden">
              <div className="h-full bg-green-500" style={{ width: `${Math.min(volume * 3, 100)}%` }} />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">API Key</label>
            <input
              type="password"
              className="w-full border rounded p-2 text-sm"
              value={apiKey}
              onInput={e => setApiKey((e.target as HTMLInputElement).value)}
              placeholder="API Key"
            />
          </div>
        </div>

        <div className="flex-1 border rounded p-4 mb-4 overflow-y-auto space-y-2 bg-gray-50">
          {messages.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'text-right text-black' : 'text-left text-gray-600'}>
              {m.content}
            </div>
          ))}
        </div>

        <textarea
          className="w-full border rounded p-2 text-sm"
          rows={3}
          value={input}
          onInput={e => setInput((e.target as HTMLInputElement).value)}
          placeholder="Type your message..."
        ></textarea>

        <div className="flex justify-between pt-4">
          <button onClick={startRecording} className="border px-4 py-2 rounded text-sm hover:bg-gray-100">
            🎙️ Record
          </button>
          <button onClick={handleSendMessage} className="bg-black text-white px-4 py-2 rounded text-sm hover:bg-gray-800">
            ➤ Send
          </button>
        </div>
      </main>
    </div>
  );
}
