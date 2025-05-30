import os
import pytest
import numpy as np
from unittest.mock import patch, MagicMock


from engine import voice

# Skip all tests if running in CI environment or if explicitly marked to skip audio tests
# This allows tests to run in environments without audio hardware
skip_all = pytest.mark.skipif(
    os.environ.get("CI") == "true" or os.environ.get("SKIP_AUDIO_TESTS") == "true",
    reason="Skipping audio tests in CI environment or when SKIP_AUDIO_TESTS is set"
)

# Test data
SAMPLE_AUDIO = np.zeros((16000,), dtype=np.int16)  # 1 second of silence
SAMPLE_AUDIO_WITH_SPEECH = np.random.randint(-32768, 32767, (16000,), dtype=np.int16)  # 1 second of random noise

@pytest.mark.expensive
class TestVoice:

    @pytest.fixture
    def mock_sounddevice(self):
        """Mock sounddevice for testing audio recording functions."""
        with patch('engine.voice.sd') as mock_sd:
            # Configure the mock to return sample audio when recording
            mock_sd.rec.return_value = SAMPLE_AUDIO.reshape(-1, 1)  # Reshape to match channels dimension

            # Mock the InputStream context manager
            mock_stream = MagicMock()
            mock_sd.InputStream.return_value.__enter__.return_value = mock_stream

            # Mock CallbackStop as a proper exception class
            class CallbackStop(Exception):
                pass
            mock_sd.CallbackStop = CallbackStop

            yield mock_sd

    @pytest.fixture
    def mock_whisper(self):
        """Mock whisper for testing transcription functions."""
        with patch('engine.voice.whisper') as mock_whisper:
            # Configure the mock model
            mock_model = MagicMock()
            mock_model.transcribe.return_value = {"text": "sample transcription"}
            mock_whisper.load_model.return_value = mock_model

            yield mock_whisper

    @pytest.fixture
    def mock_tts(self):
        """Mock TTS for testing speech synthesis functions."""
        with patch('engine.voice.TTS') as mock_tts_class:
            # Configure the mock TTS instance
            mock_tts_instance = MagicMock()
            mock_tts_instance.tts.return_value = np.zeros((22050,), dtype=np.float32)  # 1 second of silence at 22050Hz
            mock_tts_class.return_value = mock_tts_instance

            yield mock_tts_class

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess for testing audio playback."""
        with patch('engine.voice.subprocess') as mock_subprocess:
            yield mock_subprocess

    @pytest.fixture
    def mock_soundfile(self):
        """Mock soundfile for testing audio file operations."""
        with patch('engine.voice.sf') as mock_sf:
            yield mock_sf

    @skip_all
    def test_get_whisper_model(self, mock_whisper):
        """Test that get_whisper_model loads the model correctly."""
        # Reset the global model
        voice._model = None

        # Call the function
        model = voice.get_whisper_model()

        # Verify the model was loaded
        assert mock_whisper.load_model.called
        assert mock_whisper.load_model.call_args[0][0] == "base"
        assert model == mock_whisper.load_model.return_value

        # Call again to test caching
        voice.get_whisper_model()

        # Verify the model was only loaded once
        assert mock_whisper.load_model.call_count == 1

    @skip_all
    def test_record_audio(self, mock_sounddevice):
        """Test that record_audio records audio correctly."""
        # Call the function
        audio = voice.record_audio(duration=1, samplerate=16000)

        # Verify sounddevice.rec was called with correct parameters
        mock_sounddevice.rec.assert_called_once()
        args, kwargs = mock_sounddevice.rec.call_args
        assert args[0] == 16000  # 1 second at 16000Hz
        assert kwargs['samplerate'] == 16000
        assert kwargs['channels'] == 1
        assert kwargs['dtype'] == np.int16

        # Verify sounddevice.wait was called
        assert mock_sounddevice.wait.called

        # Verify the returned audio
        np.testing.assert_array_equal(audio, SAMPLE_AUDIO)

    @skip_all
    def test_estimate_noise_floor(self, mock_sounddevice):
        """Test that estimate_noise_floor measures background noise correctly."""
        # Call the function
        noise_floor = voice.estimate_noise_floor(duration=0.2, samplerate=16000)

        # Verify sounddevice.rec was called with correct parameters
        mock_sounddevice.rec.assert_called_once()
        args, kwargs = mock_sounddevice.rec.call_args
        assert args[0] == 3200  # 0.2 seconds at 16000Hz
        assert kwargs['samplerate'] == 16000
        assert kwargs['channels'] == 1
        assert kwargs['dtype'] == np.int16

        # Verify sounddevice.wait was called
        assert mock_sounddevice.wait.called

        # Verify the returned noise floor is a number
        assert isinstance(noise_floor, (int, float))

    @skip_all
    def test_record_audio_until_silence_no_speech(self, mock_sounddevice):
        """Test record_audio_until_silence when no speech is detected."""
        # Configure the mock to simulate no speech (volume below threshold)
        def callback_side_effect(*args, **kwargs):
            # Extract the callback function
            callback = kwargs.get('callback')
            # Create dummy indata with low volume
            indata = np.zeros((1000, 1), dtype=np.int16)
            # Call the callback with the dummy data
            callback(indata, 1000, None, None)
            # Sleep for a moment to simulate recording
            import time
            time.sleep(0.1)

        mock_sounddevice.InputStream.side_effect = callback_side_effect

        # Call the function
        audio = voice.record_audio_until_silence(threshold=1000, max_duration=1)

        # Verify the returned audio is empty (zeros)
        assert audio.shape == (1,)
        assert np.all(audio == 0)

    @skip_all
    def test_record_audio_until_silence_none_stream(self, mock_sounddevice):
        """Test record_audio_until_silence when InputStream returns None."""
        # Configure the mock to return None for InputStream
        mock_sounddevice.InputStream.return_value = None

        # Call the function
        audio = voice.record_audio_until_silence()

        # Verify the returned audio is empty (zeros)
        assert audio.shape == (1,)
        assert np.all(audio == 0)

    @skip_all
    def test_record_audio_until_silence_context_manager_error(self, mock_sounddevice):
        """Test record_audio_until_silence when InputStream doesn't support context manager."""
        # Create a mock stream that raises TypeError when used as a context manager
        mock_stream = MagicMock()

        # Configure the __enter__ method to raise a TypeError
        def enter_side_effect():
            raise TypeError("'NoneType' object does not support the context manager protocol")

        mock_stream.__enter__.side_effect = enter_side_effect

        # Configure methods for the fallback approach
        mock_stream.start = MagicMock()
        mock_stream.stop = MagicMock()
        mock_stream.close = MagicMock()

        # Configure the mock to return our problematic stream
        mock_sounddevice.InputStream.return_value = mock_stream

        # Call the function
        audio = voice.record_audio_until_silence()

        # Verify the fallback approach was used
        assert mock_stream.start.called
        assert mock_stream.stop.called
        assert mock_stream.close.called

        # Verify the returned audio is empty (zeros)
        assert audio.shape == (1,)
        assert np.all(audio == 0)

    @skip_all
    def test_save_temp_wav(self):
        """Test that save_temp_wav saves audio to a temporary file correctly."""
        with patch('tempfile.NamedTemporaryFile') as mock_temp_file, \
             patch('scipy.io.wavfile.write') as mock_write:

            # Configure the mock temporary file
            mock_temp = MagicMock()
            mock_temp.name = "/tmp/test.wav"
            mock_temp_file.return_value.__enter__.return_value = mock_temp

            # Call the function
            file_path = voice.save_temp_wav(SAMPLE_AUDIO)

            # Verify the audio was written to the file
            mock_write.assert_called_once()
            args, kwargs = mock_write.call_args
            assert args[0] == "/tmp/test.wav"
            assert args[1] == 16000
            np.testing.assert_array_equal(args[2], SAMPLE_AUDIO)

            # Verify the returned file path
            assert file_path == "/tmp/test.wav"

    @skip_all
    def test_transcribe_audio(self, mock_whisper):
        """Test that transcribe_audio transcribes speech correctly."""
        with patch('engine.voice.record_audio_until_silence', return_value=SAMPLE_AUDIO), \
             patch('engine.voice.save_temp_wav', return_value="/tmp/test.wav"), \
             patch('engine.voice.get_whisper_model', return_value=mock_whisper.load_model.return_value), \
             patch('os.remove') as mock_remove:

            # Call the function
            text = voice.transcribe_audio()

            # Verify the model was used to transcribe
            model = mock_whisper.load_model.return_value
            model.transcribe.assert_called_once_with("/tmp/test.wav")

            # Verify the temporary file was removed
            mock_remove.assert_called_once_with("/tmp/test.wav")

            # Verify the returned text
            assert text == "sample transcription"

    @skip_all
    def test_transcribe_audio_file_not_found(self, mock_whisper):
        """Test that transcribe_audio handles FileNotFoundError gracefully."""
        with patch('engine.voice.record_audio_until_silence', return_value=SAMPLE_AUDIO), \
             patch('engine.voice.save_temp_wav', return_value="/tmp/test.wav"), \
             patch('engine.voice.get_whisper_model', return_value=mock_whisper.load_model.return_value), \
             patch('os.remove', side_effect=FileNotFoundError("File not found")), \
             patch('builtins.print') as mock_print:

            # Call the function - should not raise an exception
            text = voice.transcribe_audio()

            # Verify the model was used to transcribe
            model = mock_whisper.load_model.return_value
            model.transcribe.assert_called_once_with("/tmp/test.wav")

            # Verify the warning was printed
            mock_print.assert_any_call("⚠️ Warning: Could not remove temporary file /tmp/test.wav: File not found")

            # Verify the returned text
            assert text == "sample transcription"

    @skip_all
    def test_speak_text(self, mock_tts, mock_soundfile, mock_subprocess):
        """Test that speak_text generates and plays speech correctly."""
        # Reset the global TTS model
        voice._tts = None

        # Configure subprocess.run to succeed for ffplay -version
        mock_subprocess.run.return_value.returncode = 0

        # Call the function
        voice.speak_text("Hello, world!")

        # Verify TTS was initialized
        mock_tts.assert_called_once_with(
            model_name="tts_models/en/ljspeech/tacotron2-DDC",
            progress_bar=False,
            gpu=False
        )

        # Verify TTS was used to generate speech
        mock_tts_instance = mock_tts.return_value
        mock_tts_instance.tts.assert_called_once_with("Hello, world!")

        # Verify the audio was saved to a file
        mock_soundfile.write.assert_called_once()
        args, kwargs = mock_soundfile.write.call_args
        # Check that the filename contains "speech_" and ends with ".wav"
        assert "speech_" in args[0]
        assert args[0].endswith(".wav")
        assert args[2] == 22050

        # Verify ffplay was called to play the audio
        mock_subprocess.run.assert_called_once()
        args, kwargs = mock_subprocess.run.call_args
        cmd = args[0]
        assert cmd[:3] == ["ffplay", "-nodisp", "-autoexit"]
        assert os.path.isabs(cmd[3]) and "speech_" in cmd[3] and cmd[3].endswith(".wav")
        assert kwargs['stdout'] == mock_subprocess.DEVNULL
        assert kwargs['stderr'] == mock_subprocess.DEVNULL

    @skip_all
    def test_speak_text_multiarray_error(self, mock_tts, mock_soundfile, mock_subprocess):
        """Test that speak_text handles numpy multiarray errors correctly."""
        # Reset the global TTS model
        voice._tts = None

        # Configure subprocess.run to succeed for ffplay -version
        mock_subprocess.run.return_value.returncode = 0

        # Configure the mock to raise an AttributeError on first call, then succeed
        mock_tts_instance = mock_tts.return_value
        mock_tts_instance.tts.side_effect = [
            AttributeError("module 'numpy._core' has no attribute 'multiarray'"),
            np.zeros((22050,), dtype=np.float32)
        ]

        # Call the function
        voice.speak_text("Hello, world!")

        # Verify TTS was called twice (once failing, once succeeding)
        assert mock_tts_instance.tts.call_count == 2

        # Verify the audio was saved to a file
        mock_soundfile.write.assert_called_once()

        # Verify ffplay version check was called
        assert mock_subprocess.run.call_count >= 1

    @skip_all
    def test_speak_text_generator_output(self, mock_tts, mock_soundfile, mock_subprocess):
        """Test that speak_text handles generator output from TTS correctly."""
        # Reset the global TTS model
        voice._tts = None

        # Configure subprocess.run to succeed for ffplay -version
        mock_subprocess.run.return_value.returncode = 0

        # Configure the mock to return a generator
        def generator_output():
            for i in range(10):
                yield np.zeros((2205,), dtype=np.float32)

        mock_tts_instance = mock_tts.return_value
        mock_tts_instance.tts.return_value = generator_output()

        # Call the function
        voice.speak_text("Hello, world!")

        # Verify the audio was saved to a file
        mock_soundfile.write.assert_called_once()

        # The generator should have been converted to a list
        args, kwargs = mock_soundfile.write.call_args
        assert isinstance(args[1], (list, np.ndarray))

        # Verify ffplay version check was called
        assert mock_subprocess.run.call_count >= 1

    @skip_all
    def test_speak_text_file_not_found(self, mock_tts, mock_soundfile, mock_subprocess):
        """Test that speak_text handles FileNotFoundError gracefully when removing the speech file."""
        # Reset the global TTS model
        voice._tts = None

        # Configure subprocess.run to succeed for ffplay -version
        mock_subprocess.run.return_value.returncode = 0

        # Configure the mock to return audio data
        mock_tts_instance = mock_tts.return_value
        mock_tts_instance.tts.return_value = np.zeros((22050,), dtype=np.float32)

        # Mock os.remove to raise FileNotFoundError
        with patch('os.remove', side_effect=FileNotFoundError("File not found")), \
             patch('builtins.print') as mock_print:

            # Call the function - should not raise an exception
            voice.speak_text("Hello, world!")

            # Verify TTS was used to generate speech
            mock_tts_instance.tts.assert_called_once_with("Hello, world!")

            # Verify the audio was saved to a file
            mock_soundfile.write.assert_called_once()

            # Verify the warning was printed
            # We can't check the exact file path since it contains a UUID, but we can check part of the message
            warning_calls = [call for call in mock_print.call_args_list if "⚠️ Warning: Could not remove speech file" in str(call)]
            assert len(warning_calls) > 0
