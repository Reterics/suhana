import { useEffect, useRef, useState } from 'preact/hooks';
import { Mic, SendHorizontal, Settings } from 'lucide-preact';
import { useChat } from '../context/ChatContext.tsx';
import Microphone from "../assets/microphone.svg?react"

interface Props {
  onSend: (message: string) => void;
  initialInput?: string;
}

export function ChatToolbar({ onSend, initialInput }: Props) {
  const { apiKey, setApiKey, transcribe } = useChat();

  const [input, setInput] = useState('');

  // Prefill input when coming from Welcome screen
  // TODO: Use context for this
  useEffect(() => {
    if (typeof initialInput === 'string') {
      setInput(initialInput);
    }
  }, [initialInput]);

  const [volume, setVolume] = useState(0);
  const [micDeviceId, setMicDeviceId] = useState<string>('');
  const [micDevices, setMicDevices] = useState<MediaDeviceInfo[]>([]);
  const [micTestStatus, setMicTestStatus] = useState<
    'pending' | 'success' | 'fail' | null
  >(null);
  const [showMicSelector, setShowMicSelector] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [recording, setRecording] = useState(false);
  const segmentCount = 10;
  const activeSegments = Math.round(Math.min(volume * 0.2, segmentCount));
  const enterCountRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout>| null>(null);

  const intervalRef = useRef<number>();
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    navigator.mediaDevices
      .enumerateDevices()
      .then(devices =>
        setMicDevices(devices.filter(d => d.kind === 'audioinput'))
      );
  }, []);

  async function testMic(deviceId: string) {
    setMicTestStatus('pending');
    const constraints = deviceId
      ? { audio: { deviceId: { exact: deviceId } } }
      : { audio: true };
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
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

  async function startRecording() {
    setRecording(true);
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
      setRecording(false);
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
      const avg =
        data.reduce((sum, val) => sum + Math.abs(val - 128), 0) / data.length;
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

  const sendMessage = () => {
    const message = input.trim();
    if (message) {
      onSend(message);
      setInput('');
    }
  };

  const onKeyUp = (e: KeyboardEvent) => {
    setInput((e.target as HTMLInputElement).value)

    if (e.key === 'Enter') {
      enterCountRef.current += 1;

      if (enterCountRef.current === 2) {
        enterCountRef.current = 0;
        if (timerRef.current) clearTimeout(timerRef.current);
        sendMessage();
        return;
      }

      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        enterCountRef.current = 0;
      }, 1000);
    }
  }

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  return (
    <div className="p-3 border-t border-t-gray-300 bg-white space-y-1">
      <textarea
        ref={inputRef}
        rows={2}
        value={input}
        placeholder="Type a message..."
        onKeyUp={onKeyUp}
        className="w-full border border-gray-300 rounded px-3 py-2 resize-none bg-neutral-50 shadow-sm focus:outline-none focus:ring-1 focus:ring-gray"
      />

      <div
        className="flex items-center justify-between transition-all duration-300 ease-in-out min-h-8"
      >
        <div className="flex items-center gap-3 text-gray-500 flex-wrap">
          <button
            onClick={() => {
              setShowMicSelector(prev => {
                setShowApiKey(false);
                return !prev;
              });
            }}
            title="Microphone"
            data-testid="microphone-button"
          >
            <Microphone className="h-5 w-5 hover:text-black" />
          </button>
          <button
            onClick={() => {
              setShowApiKey(prev => {
                setShowMicSelector(false);
                return !prev;
              });
            }}
            title="Settings"
          >
            <Settings className="h-5 w-5 hover:text-black" />
          </button>

          <div>
            <div
              className={`flex place-items-center justify-center transition-all duration-300 ease-in-out overflow-hidden mb-0 ${
                showApiKey ? 'opacity-100 w-full' : 'opacity-0 w-0 h-0'
              }`}
            >
              <div className="pe-2">API:</div>
              <input
                type="password"
                className="w-full border border-zinc-300 rounded px-3 py-1 text-sm bg-neutral-50"
                value={apiKey}
                onInput={e => setApiKey((e.target as HTMLInputElement).value)}
                placeholder="API Key"
              />
            </div>

            <div
              className={`flex transition-all duration-300 ease-in-out overflow-hidden mb-0 ${
                showMicSelector ? 'opacity-100 w-full' : 'opacity-0 w-0 h-0'
              }`}
            >
              <select
                value={micDeviceId}
                onChange={e => {
                  const id = e.currentTarget.value;
                  setMicDeviceId(id);
                  void testMic(id);
                }}
                className="w-40 border border-zinc-300 rounded p-1 text-sm bg-neutral-50"
              >
                <option value="">(Default Microphone)</option>
                {micDevices.map((d, i) => (
                  <option key={i} value={d.deviceId}>
                    {d.label || `Mic ${i}`}
                  </option>
                ))}
              </select>
              {micTestStatus && (
                <div className="text-xs px-2 self-center flex w-34 text-nowrap">
                  Mic Test:{' '}
                  {micTestStatus === 'success'
                    ? '✅ Working'
                    : micTestStatus === 'fail'
                      ? '❌ No input'
                      : '⏳ Testing...'}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 text-gray-500">
          {recording && (
            <div className="flex h-4 w-28 max-w-full">
              {Array.from({ length: segmentCount }).map((_, i) => (
                <div
                  key={i}
                  className={`w-full h-full ${
                    i < activeSegments ? 'bg-green-500' : 'bg-gray-200'
                  }`}
                />
              ))}
            </div>
          )}

          <button onClick={startRecording} title="Record">
            <Mic className="h-5 w-5 hover:text-black" />
          </button>
          <button
            onClick={sendMessage}
            className="text-white bg-black p-2 rounded hover:bg-gray-800"
            title="Send"
          >
            <SendHorizontal className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
