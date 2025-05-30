# Suhana Testing Guide

This document provides information on how to run and write tests for the Suhana project, with a special focus on testing components that depend on hardware or external services.

## Test Coverage

The following modules have comprehensive test coverage:

### 1. error_handling.py (16 tests)
Tests for the error handling system in `engine/error_handling.py`.

- **Basic Error Classes**
  - Tests for SuhanaError and all specific error types (ConfigurationError, BackendError, MemoryError, VectorStoreError, ToolError, NetworkError)
- **Error Handling**
  - Tests for handling SuhanaError, standard exceptions, and error handlers
- **Error Boundary**
  - Tests for the error boundary decorator with various configurations
- **Utilities**
  - Tests for error formatting and default error handling

### 2. memory_store.py (9 tests)
Tests for the memory store system in `engine/memory_store.py`.

- Tests for loading, saving, adding, searching, recalling, and forgetting memory

### 3. engine_config.py (8 tests)
Tests for the configuration system in `engine/engine_config.py`.

- Tests for loading and saving settings, configuring logging, and switching backends

### 4. utils.py (7 tests)
Tests for utility functions in `engine/utils.py`.

- Tests for logging configuration, embedding models, and vector store operations

### Modules Needing Test Coverage

The following modules now have test coverage:
- conversation_store.py ✓
- history.py ✓
- interfaces.py ✓
- net.py ✓
- tool_store.py ✓

However, the coverage for these modules is still relatively low and could be improved. Additionally, the following modules need better test coverage:
- tools/*.py (most tool modules have low or no coverage)
- api_server.py
- ingest.py
- ingest_project.py
- main.py

## Test Organization

The tests are organized into two main directories:

- `tests/unit/`: Contains tests that are fast, deterministic, and don't require special hardware or external services. These tests should always run in CI.
- `tests/integration/`: Contains tests that are slow, expensive, or require special hardware or external services. These tests should only run locally.

### Expensive Tests

Tests that require special hardware, external services, or are otherwise expensive to run are marked with the `@pytest.mark.expensive` decorator. These tests are skipped by default in CI environments.

Examples of expensive tests include:
- Tests that use real LLM APIs (OpenAI, etc.)
- Tests that require audio hardware (microphone, speakers)
- Tests that download large models
- Tests that make real web requests

## Running Tests

To run all tests (excluding expensive tests):

```bash
python -m pytest
```

To run all tests, including expensive tests:

```bash
python -m pytest --runexpensive
```

To run only unit tests:

```bash
python -m pytest tests/unit/
```

To run only integration tests:

```bash
python -m pytest tests/integration/
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
python -m pytest --cov --cov-config=.coveragerc
```

## Code Coverage

The project includes code coverage reporting in the GitHub Actions CI pipeline. The coverage report is generated using pytest-cov and uploaded to Codecov.

### Coverage Configuration

The `.coveragerc` file in the project root configures code coverage reporting:

```ini
[run]
source = engine, tools, api_server.py, ingest.py, ingest_project.py, main.py
omit =
    */tests/*
    */__pycache__/*
    */venv/*
    */tauri-ui/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if __name__ == .__main__.:
    pass
    raise ImportError

[html]
directory = coverage_html_report
```

### Viewing Coverage Reports

To view the coverage report locally:

```bash
# Generate HTML report
python -m pytest --cov --cov-config=.coveragerc --cov-report=html

# Generate terminal and XML reports
python -m pytest --cov --cov-config=.coveragerc --cov-report=term --cov-report=xml
```

Then open `coverage_html_report/index.html` in your browser.

### CI Pipeline Coverage

The GitHub Actions workflow runs tests with coverage reporting and uploads the results to Codecov. The workflow is configured to:

1. Run tests with coverage reporting
2. Generate XML and terminal reports
3. Upload the coverage report to Codecov
4. Check that coverage meets a minimum threshold (currently 30%)

You can view the coverage reports in the GitHub Actions workflow logs and on Codecov.

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

1. Use the `@pytest.mark.expensive` decorator to mark tests that should only run locally
2. Place these tests in the `tests/integration/` directory
3. Use mocking to simulate hardware and external dependencies
4. Test both normal operation and error handling
5. Consider different environments (Windows, macOS, Linux) and their specific requirements

Example using the new approach:

```python
@pytest.mark.expensive
def test_record_audio(mock_sounddevice):
    # Test code here
    pass
```

For backward compatibility, you can also use the `@pytest.mark.skipif` decorator:

```python
@pytest.mark.skipif(
    os.environ.get("CI") == "true" or os.environ.get("SKIP_AUDIO_TESTS") == "true",
    reason="Skipping audio tests in CI environment or when SKIP_AUDIO_TESTS is set"
)
def test_record_audio(mock_sounddevice):
    # Test code here
    pass
```

The recommended approach is to use `@pytest.mark.expensive` for new tests and gradually migrate existing tests to this approach.

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
