#!/bin/bash

set -e

echo "🔧 Starting setup for Suhana (Unix/macOS)"

# 1. Check Python
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 is not installed. Please install Python 3.11+."
  exit 1
fi

# 2. Check Ollama
if ! command -v ollama &>/dev/null; then
  echo "❌ Ollama is not installed."
  echo "➡️  Install from https://ollama.com/download and rerun this script."
  exit 1
fi

# 3. Create and activate virtualenv
if [ ! -d "venv" ]; then
  python3 -m venv venv
  echo "✅ Virtual environment created."
fi
source venv/bin/activate

# 4. Install Python deps
pip install --upgrade pip
pip install -r requirements.txt

# 5. Launch
python3 main.py
