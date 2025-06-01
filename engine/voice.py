import os
import uuid
import tempfile
import subprocess
import sounddevice as sd
import numpy as np

# Ensure numpy._core.multiarray is properly initialized before importing TTS
# This prevents the "AttributeError: module 'numpy._core' has no attribute 'multiarray'" error
try:
    import numpy._core.multiarray
except (ImportError, AttributeError):
    # If multiarray is not available, create a minimal implementation
    # This is a workaround for compatibility with PyTorch 2.4+ and TTS
    if not hasattr(np._core, 'multiarray'):
        class DummyMultiarray:
            class scalar:
                pass
        np._core.multiarray = DummyMultiarray()

# Make sure the multiarray attribute is accessible to other modules
# This ensures that when TTS imports numpy, it can find the multiarray attribute
if hasattr(np._core, 'multiarray') and not hasattr(np, '_MULTIARRAY_PATCHED'):
    # Mark that we've patched numpy to avoid doing it multiple times
    np._MULTIARRAY_PATCHED = True
    # Ensure the multiarray module is properly exposed in numpy's namespace
    if not hasattr(np, 'multiarray'):
        np.multiarray = np._core.multiarray

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
    try:
        baseline = estimate_noise_floor()
        threshold = baseline + 50
    except Exception as e:
        print(f"⚠️ estimate_noise_floor failed: {e}, falling back to manual recording...")
        audio = record_audio(duration=5)
        return audio.flatten() if hasattr(audio, "flatten") else audio

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

    # Create the InputStream
    stream = sd.InputStream(callback=callback, samplerate=samplerate, channels=1, dtype=np.int16, blocksize=frame_samples)

    # Check if stream is None (which would cause the TypeError)
    if stream is None:
        print("⚠️ Failed to create audio input stream. Check your audio device configuration.")
        return np.zeros((1,), dtype=np.int16)

    try:
        # Try to use the stream as a context manager
        with stream:
            sd.sleep(int(max_duration * 1000))
    except sd.CallbackStop:
        pass  # expected exit
    except TypeError as e:
        if "context manager protocol" in str(e):
            print("⚠️ Audio input stream doesn't support context manager. Using manual start/stop instead.")
            try:
                # Alternative approach without context manager
                stream.start()
                sd.sleep(int(max_duration * 1000))
                stream.stop()
                stream.close()
            except sd.CallbackStop:
                pass  # expected exit
            except Exception as e:
                print(f"❌ Error recording audio: {e}")
                return np.zeros((1,), dtype=np.int16)
        else:
            # Re-raise other TypeError exceptions
            raise

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
    try:
        os.remove(wav_path)
    except FileNotFoundError as e:
        print(f"⚠️ Warning: Could not remove temporary file {wav_path}: {e}")
    return result["text"]

def speak_text(text):
    global _tts
    if _tts is None:
        print("🔊 Initializing text-to-speech engine...")
        _tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False, gpu=False)
    print("🔊 Generating speech...")
    try:
        wav = _tts.tts(text)
    except AttributeError as e:
        if "multiarray" in str(e):
            print(f"⚠️ NumPy multiarray error: {e}")
            print("🔄 Attempting to fix NumPy multiarray issue and retry...")
            # Ensure multiarray is available in numpy's namespace
            if hasattr(np._core, 'multiarray'):
                np.multiarray = np._core.multiarray
            # Try again
            wav = _tts.tts(text)
        else:
            raise

    # Handle case where tts() returns a generator
    if hasattr(wav, '__iter__') and not isinstance(wav, (bytes, str, list, np.ndarray)):
        print("🔄 Converting generator to list...")
        try:
            wav = list(wav)  # Convert generator to list
        except Exception as e:
            print(f"⚠️ Error converting generator to list: {e}")
            # Try to consume the generator in a different way
            wav = [item for item in wav]

    # Ensure wav is a proper format for sf.write
    if isinstance(wav, (list, tuple)) and len(wav) > 0 and isinstance(wav[0], (list, tuple, np.ndarray)):
        print("🔄 Flattening nested list/array...")
        wav = np.concatenate([np.array(item) for item in wav])

    # Use absolute path for the speech file
    speech_file = os.path.abspath(f"speech_{uuid.uuid4().hex}.wav")
    print("🔊 Writing audio to file: ", speech_file)
    sf.write(speech_file, wav, 22050)

    try:
        print("🔊 Playing audio...")
        subprocess.run(["ffplay", "-nodisp", "-autoexit", speech_file], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, shell=True)
    finally:
        try:
            os.remove(speech_file)
        except FileNotFoundError as e:
            print(f"⚠️ Warning: Could not remove speech file {speech_file}: {e}")
