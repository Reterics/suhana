# Suhana Testing Guide

This document provides information on how to run and write tests for the Suhana project, with a special focus on testing components that depend on hardware or external services.

## Running Tests

To run all tests:

```bash
python -m pytest
```

To run specific tests:

```bash
# Run a specific test file (Linux/macOS)
python -m pytest tests/test_voice.py
# Run a specific test file (Windows)
python -m pytest tests\test_voice.py

# Run a specific test (Linux/macOS)
python -m pytest tests/test_voice.py::TestVoice::test_speak_text
# Run a specific test (Windows)
python -m pytest tests\test_voice.py::TestVoice::test_speak_text

# Run with verbose output
python -m pytest -v

# Run with coverage report
python -m pytest --cov=engine
```

## Testing Hardware-Dependent Components

Some components in Suhana, like `voice.py`, depend on hardware (microphone, speakers) or external services. Testing these components requires special consideration.

### Skipping Audio Tests

Audio tests are skipped by default in CI environments or when the `SKIP_AUDIO_TESTS` environment variable is set to `true`. This allows tests to run in environments without audio hardware.

To skip audio tests:

```bash
# Windows (Command Prompt)
set SKIP_AUDIO_TESTS=true
python -m pytest

# Windows (PowerShell)
$env:SKIP_AUDIO_TESTS="true"
python -m pytest

# Linux/macOS
SKIP_AUDIO_TESTS=true python -m pytest
```

### Testing in Different Environments

To ensure that voice.py works in every environment, tests use mocking to simulate hardware and external dependencies. This allows the tests to run without actual hardware.

However, it's also important to test with real hardware occasionally. To do this:

1. Make sure your environment has a microphone and speakers
2. Make sure ffmpeg is installed and available in your PATH
3. Run the tests without the SKIP_AUDIO_TESTS environment variable

```bash
# Linux/macOS
python -m pytest tests/test_voice.py

# Windows
python -m pytest tests\test_voice.py
```

## Writing Tests for Hardware-Dependent Components

When writing tests for components that depend on hardware or external services:

1. Use the `@pytest.mark.skipif` decorator to skip tests in environments where they can't run
2. Use mocking to simulate hardware and external dependencies
3. Test both normal operation and error handling
4. Consider different environments (Windows, macOS, Linux) and their specific requirements

Example:

```python
@pytest.mark.skipif(
    os.environ.get("CI") == "true" or os.environ.get("SKIP_AUDIO_TESTS") == "true",
    reason="Skipping audio tests in CI environment or when SKIP_AUDIO_TESTS is set"
)
def test_record_audio(mock_sounddevice):
    # Test code here
    pass
```

## Testing voice.py

The `test_voice.py` file contains tests for all functions in `voice.py`. These tests use mocking to simulate hardware and external dependencies, allowing them to run in any environment.

The tests cover:

1. Recording audio (`record_audio`, `record_audio_until_silence`)
2. Measuring background noise (`estimate_noise_floor`)
3. Saving audio to a file (`save_temp_wav`)
4. Transcribing audio (`transcribe_audio`)
5. Converting text to speech (`speak_text`)

The tests also cover error handling, such as:

1. Handling numpy multiarray errors
2. Handling generator output from TTS

To run these tests with real hardware, make sure your environment has a microphone and speakers, and run:

```bash
python -m pytest tests/test_voice.py
```

To run these tests without real hardware, set the SKIP_AUDIO_TESTS environment variable:

```bash
# Windows (Command Prompt)
set SKIP_AUDIO_TESTS=true
python -m pytest tests\test_voice.py

# Windows (PowerShell)
$env:SKIP_AUDIO_TESTS="true"
python -m pytest tests\test_voice.py

# Linux/macOS
SKIP_AUDIO_TESTS=true python -m pytest tests/test_voice.py
```
