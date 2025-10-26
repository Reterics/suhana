@echo off
setlocal enabledelayedexpansion
set PYTHON_BIN=python
set VENV_DIR=.venv-ci
set REQ_FILE=requirements-ci.txt

echo Setting up CI virtual environment

REM Step 1: Create venv if not exists
if not exist "%VENV_DIR%" (
    echo Creating virtual environment: %VENV_DIR%
    %PYTHON_BIN% -m venv "%VENV_DIR%"
)

call "%VENV_DIR%\Scripts\activate.bat"

REM Step 2: Upgrade pip & install dependencies
echo Installing dependencies from %REQ_FILE%
python -m pip install --upgrade pip wheel setuptools
python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r "%REQ_FILE%"
if errorlevel 1 (
    echo Dependency installation failed.
    exit /b 1
)

REM Step 3: Run tests
echo Running tests...
python -m pytest --disable-warnings --cov=engine --cov-report=term
if errorlevel 1 (
    echo Tests failed.
    exit /b 1
)

echo All tests completed successfully!

endlocal
