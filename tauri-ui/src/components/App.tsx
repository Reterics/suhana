import { useEffect, useRef, useState } from 'preact/hooks';

export function App() {
  const [apiKey, setApiKey] = useState(
    localStorage.getItem('suhana_key') || 'YOUR_API_KEY_HERE'
  );
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<string[]>([]);
  const [volume, setVolume] = useState(0);
  const [micDeviceId, setMicDeviceId] = useState<string>('');
  const [micDevices, setMicDevices] = useState<MediaDeviceInfo[]>([]);
  const [micTestStatus, setMicTestStatus] = useState<
    'pending' | 'success' | 'fail' | null
  >(null);

  const intervalRef = useRef<number>();

  useEffect(() => {
    navigator.mediaDevices.enumerateDevices().then(devices => {
      const mics = devices.filter(d => d.kind === 'audioinput');
      setMicDevices(mics);
    });
  }, []);

  async function testMic(deviceId: string) {
    setMicTestStatus('pending');
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { deviceId: { exact: deviceId } }
    });

    const context = new AudioContext();
    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    const data = new Uint8Array(analyser.fftSize);
    source.connect(analyser);

    let maxVolume = 0;

    intervalRef.current = window.setInterval(() => {
      analyser.getByteTimeDomainData(data);
      const avg =
        data.reduce((sum, val) => sum + Math.abs(val - 128), 0) / data.length;
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

  async function sendMessage() {
    if (!input.trim()) return;

    const response = await fetch('http://localhost:8000/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey
      },
      body: JSON.stringify({ input, backend: 'ollama' })
    });

    const data = await response.json();
    setMessages(prev => [...prev, `You: ${input}`, `Suhana: ${data.response}`]);
    setInput('');
    localStorage.setItem('suhana_key', apiKey);
  }

  async function startRecording() {
    const constraints = micDeviceId
      ? { deviceId: { exact: micDeviceId } }
      : true;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: constraints
    });

    const context = new AudioContext();
    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    const data = new Uint8Array(analyser.fftSize);
    source.connect(analyser);

    const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    const chunks: Blob[] = [];

    recorder.ondataavailable = e => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    recorder.onstop = async () => {
      clearInterval(intervalRef.current);
      setVolume(0);
      stream.getTracks().forEach(track => track.stop());

      const blob = new Blob(chunks, { type: 'audio/webm' });
      const form = new FormData();
      form.append('audio', blob, 'speech.webm');

      const res = await fetch('http://localhost:8000/transcribe', {
        method: 'POST',
        body: form
      });

      const { text } = await res.json();
      setInput(text);
    };

    recorder.start();

    let silenceStart: number | null = null;
    const silenceThreshold = 3; // seconds of silence to stop
    const volumeThreshold = 5; // below this = silence

    intervalRef.current = window.setInterval(() => {
      analyser.getByteTimeDomainData(data);
      const avg =
        data.reduce((sum, val) => sum + Math.abs(val - 128), 0) / data.length;
      setVolume(avg);

      const now = Date.now();
      if (avg < volumeThreshold) {
        if (silenceStart === null) {
          silenceStart = now;
        } else if (now - silenceStart > silenceThreshold * 1000) {
          recorder.stop();
        }
      } else {
        silenceStart = null;
      }
    }, 200);
  }

  return (
    <div>
      <h1>
        <img
          src="http://localhost:8000/assets/logos/suhana_right.png"
          alt="Logo"
          style={{ maxHeight: '15vh' }}
        />
      </h1>

      <label>
        🎤 Select Microphone:
        <select
          value={micDeviceId}
          onChange={e => {
            const id = e.currentTarget.value;
            setMicDeviceId(id);
            if (id) void testMic(id);
          }}
        >
          <option value="">(Default)</option>
          {micDevices.map((d, i) => (
            <option key={i} value={d.deviceId}>
              {d.label || `Mic ${i}`}
            </option>
          ))}
        </select>
      </label>

      {micTestStatus && (
        <div style={{ marginTop: '8px', fontWeight: 'bold' }}>
          Mic Test:{' '}
          {micTestStatus === 'success'
            ? '✅ Working'
            : micTestStatus === 'fail'
              ? '❌ No input'
              : '⏳ Testing...'}
        </div>
      )}
      <div style={{ height: '8px', background: '#eee', marginTop: '10px' }}>
        <div
          style={{
            height: '8px',
            background: '#4ade80',
            width: `${Math.min(volume * 3, 100)}%`
          }}
        />
      </div>
      <br />
      <label>
        API:
        <input
          type="password"
          value={apiKey}
          onInput={e => setApiKey((e.target as HTMLInputElement).value)}
          placeholder="API Key"
        />
      </label>
      <div style={{ whiteSpace: 'pre-wrap', margin: '1em 0' }}>
        {messages.map(m => (
          <div>{m}</div>
        ))}
      </div>
      <textarea
        style={{ width: '100%', height: '100px' }}
        value={input}
        onInput={e => setInput((e.target as HTMLInputElement).value)}
        placeholder="Your message..."
      ></textarea>
      <button onClick={startRecording} style={{ float: 'left' }}>
        🎙️ Record
      </button>

      <button onClick={sendMessage} style={{ float: 'right' }}>
        Send
      </button>
    </div>
  );
}
