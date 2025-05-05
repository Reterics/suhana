import os
import tempfile
import subprocess
import sounddevice as sd
import numpy as np
import whisper
from TTS.api import TTS
import soundfile as sf
import time

_model = None
_tts = None

def get_whisper_model():
    global _model
    if _model is None:
        _model = whisper.load_model("base")  # or "tiny", "small", etc.
    return _model

def record_audio(duration=5, samplerate=16000):
    print("🎙️ Listening...")
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype=np.int16)
    sd.wait()
    return np.squeeze(recording)

def estimate_noise_floor(duration=0.2, samplerate=16000):
    print("📉 Measuring background noise...")
    audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype=np.int16)
    sd.wait()
    return np.abs(audio).mean()

def record_audio_until_silence(threshold = 100, silence_duration=2.0, max_duration=15, samplerate=16000):
    baseline = estimate_noise_floor()
    threshold = baseline + 50
    if threshold > 100:
        threshold = 100

    print("🎙️ Waiting for speech...")

    frame_duration = 0.2  # seconds
    frame_samples = int(frame_duration * samplerate)

    silence_start = None
    recording_started = False
    audio_buffer = []

    def callback(indata, frames, time_info, status):
        nonlocal silence_start, recording_started, audio_buffer
        if status:
            print(f"⚠️ {status}")

        volume = np.abs(indata).mean()
        if volume > threshold:
            if not recording_started:
                print(f"🎙️ Speech detected. {volume}/{threshold} Recording...")
                recording_started = True
            audio_buffer.append(indata.copy())
            silence_start = None
        elif recording_started:
            if silence_start is None:
                silence_start = time.time()
            elif time.time() - silence_start >= silence_duration:
                print("🛑 Silence detected. Stopping.")
                raise sd.CallbackStop()

    try:
        with sd.InputStream(callback=callback, samplerate=samplerate, channels=1, dtype=np.int16, blocksize=frame_samples):
            sd.sleep(int(max_duration * 1000))
    except sd.CallbackStop:
        pass  # expected exit

    if not audio_buffer:
        print("⚠️ No speech detected.")
        return np.zeros((1,), dtype=np.int16)

    audio = np.concatenate(audio_buffer)
    return np.squeeze(audio)

def save_temp_wav(audio, samplerate=16000):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        from scipy.io.wavfile import write
        write(f.name, samplerate, audio)
        return f.name

def transcribe_audio():
    audio = record_audio_until_silence()
    print("🎙️ Transcribing speech...")
    wav_path = save_temp_wav(audio)
    model = get_whisper_model()
    result = model.transcribe(wav_path)
    os.remove(wav_path)
    return result["text"]

def speak_text(text):
    global _tts
    if _tts is None:
        _tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False, gpu=False)
    wav = _tts.tts(text)
    sf.write("speech.wav", wav, 22050)
    subprocess.run(["ffplay", "-nodisp", "-autoexit", "speech.wav"], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    os.remove("speech.wav")
