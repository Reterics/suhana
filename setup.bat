@echo off
echo 🔧 Setting up Suhana (Windows)

REM 1. Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo ❌ Python not found. Please install Python 3.11+ and rerun.
    exit /b 1
)

REM 2. Check Ollama
where ollama >nul 2>nul
if errorlevel 1 (
    echo ❌ Ollama not found.
    echo ➡️  Please install from https://ollama.com/download and rerun.
    exit /b 1
)

REM 3. Check FFmpeg
where ffplay >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ FFmpeg not found. Please install it via https://ffmpeg.org/download.html or choco install ffmpeg
    exit /b
)

REM 4. Create venv
if not exist venv (
    python -m venv venv
    echo ✅ Virtual environment created.
)

REM 5. Activate and install deps
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

REM 5. Launch
python main.py
