![suhana_right.png](assets/logos/suhana_right.png)

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Self-hosted](https://img.shields.io/badge/self--hosted-yes-brightgreen)]()
[![Powered by](https://img.shields.io/badge/LLM-Ollama%20%7C%20OpenAI-9cf)]()
[![wakatime](https://wakatime.com/badge/user/7280a0d0-d60b-4521-a63b-d823468d18b7/project/46d7daa1-e4ae-4c9c-88f7-40193f7d5e7a.svg)](https://wakatime.com/badge/user/7280a0d0-d60b-4521-a63b-d823468d18b7/project/46d7daa1-e4ae-4c9c-88f7-40193f7d5e7a)

> Suhana _(수하나)_ is your self-hosted AI companion: a modular chat agent with a personality, local knowledge base, and the ability to run commands — all without giving away your data.


![showcase_readme.gif](assets/showcase_readme.gif)

---

## ✨ Features

- 🤖 **Chat with a personality** – Suhana remembers you and responds in character
- 🔍 **Search local knowledge** – markdown, code, and notes in `/knowledge` folder
- 🔄 **Pluggable AI engines** – supports [Ollama](https://ollama.com) (🦙) and OpenAI (🤖)
- 🧠 **Memory-aware** – Suhana evolves with you via `!remember` and `profile.json`
- 🔊 **Voice input/output** – speak naturally to Suhana and hear her reply (Whisper + Coqui)
- 🔒 **Self-hosted & portable** – no cloud dependencies, runs on macOS/Windows/Linux
- ⚡ **Execute commands** – define your own actions like `send_message()` or `update_profile()`

---

## 🚀 Quick Start

### 1. Clone the project

```bash
git clone https://github.com/Reterics/suhana.git
cd suhana
```

### 2. Install Python + Ollama (if not already installed)

You need **Python 3.11+** installed. Then choose one of the following:


#### ✅ Option A: [Ollama](https://ollama.com) — run models locally (recommended)

1. **Install Ollama**:
   - macOS / Windows: [https://ollama.com/download](https://ollama.com/download)
   - Linux:
     ```bash
     curl -fsSL https://ollama.com/install.sh | sh
     ```

2. Start a model:
   ```bash
   ollama run llama3
   ```
   > Other available models include:
   >
   > - `mistral` – lightweight and fast
   > - `llama3` – larger and more capable
   > - `gemma` – Google’s open model
   > - `phi` – compact and smart
   > - `codellama` – optimized for coding tasks
   > - `llava` – for multimodal (image + text) input

3. You can change model in `settings.template.json` or at runtime.

---

#### 🤖 Option B: OpenAI — run via cloud API

1. Add your OpenAI key in a `.env` file:
   ```dotenv
   OPENAI_API_KEY=sk-...
   ```

2. Set model and backend:
   ```json
   {
     "llm_backend": "openai",
     "openai_model": "gpt-4"
   }
   ```

> You can switch between engines at runtime using `!switch ollama` or `!switch openai`.

### 3. Run the Setup Script

#### 🐧 macOS / Linux:
```bash
./setup.sh
```

#### 🪟 Windows (CMD or PowerShell):
```cmd
setup.bat
```

> This will create a virtualenv, install dependencies, and auto-generate `settings.json` and `profile.json` if missing.

---

### 4. Ingest your knowledge files

Put `.md`, `.txt`, or `.code` files into `/knowledge`, then run:

```bash
python ingest.py
```

---

### 5. Chat with Suhana

```bash
python main.py
```

You’ll see:

```
Hello, I'm Suhana 🦙 — powered by: OLLAMA (llama3)
```

---

## 🛠 Example Commands

| Command         | Description                             |
|----------------|-----------------------------------------|
| `!engine`       | Show the current model + backend        |
| `!switch openai`| Switch between Ollama and OpenAI        |
| `!exit`         | Leave the session                       |
| `help`          | Show available tools and commands       |
| `!remember fact`| Add a memory fact                       |
| `!recall`       | List all memory facts                   |
| `!forget keyword`| Remove memory entries matching keyword |

## 🧰 Available Tools

Suhana comes with a variety of built-in tools that extend its capabilities:

| Tool           | Description                             | Example Usage                        |
|----------------|-----------------------------------------|--------------------------------------|
| `help`         | Lists available tools and commands      | "help" or "what can you do?"         |
| `get_date`     | Tells the current date                  | "what is the date today?"            |
| `get_time`     | Tells the current time                  | "what is the time now?"              |
| `add_note`     | Adds a personal note or reminder        | "remember to buy milk"               |
| `list_notes`   | Lists all stored notes by date          | "show my notes"                      |
| `update_profile`| Updates user preferences or profile    | "set preference theme to dark"       |
| `web_search`   | Searches the web using various engines  | "search for Python programming"      |
| `calculator`   | Performs basic math calculations        | "calculate 2 + 2 * 3"                |
| `weather`      | Gets current weather for a location     | "what's the weather in New York?"    |

### Web Search

The web search tool supports multiple search engines:

```
search for Python programming           # Uses DuckDuckGo by default
search with bing for machine learning   # Uses Bing search engine
search with brave for climate change    # Uses Brave search engine
```

### Calculator

The calculator tool supports various mathematical operations and functions:

- Basic arithmetic: `+`, `-`, `*`, `/`, `**` (power), `%` (modulo), `//` (floor division)
- Functions: `abs`, `round`, `min`, `max`, `sum`, `sin`, `cos`, `tan`, `sqrt`, `log`, `log10`, `exp`
- Constants: `pi`, `e`

Example: "calculate sin(pi/2) + sqrt(16)"

---

## 🧩 Folder Structure

```
suhana/
├─ engine/                # Core logic
│  ├─ agent.py            # Main loop
│  ├─ engine_config.py    # Settings and backend switching
│  ├─ profile.py          # Memory and preferences
│  ├─ history.py          # Summarization + trimming
│  └─ backends/           # ollama.py / openai.py
├─ knowledge/             # Your documents and notes
├─ vectorstore/           # Auto-generated FAISS index
├─ models/                # Prompt templates
├─ assets/                # Logos and visuals
├─ docs/                  # Documentation
│  └─ architecture.md     # Component relationships diagram
├─ ingest.py              # Knowledge indexer
├─ main.py                # Entrypoint and setup runner
├─ settings.template.json # Safe config defaults
├─ profile.json           # Runtime user profile (generated)
├─ settings.json          # Runtime config (generated)
├─ .gitignore             # Excludes local state
└─ setup.sh / setup.bat   # Easy one-step setup
```

---

## 🧠 Memory Example

A sample `profile.json`:

```json
{
  "name": "Attila",
  "preferences": {
    "communication_style": "technical, friendly"
  },
  "memory": [
    { "type": "fact", "content": "Attila prefers local models over cloud ones." }
  ]
}
```

---

## 🧠 Model Support

| Engine   | Status                   | Notes                              |
|----------|--------------------------|------------------------------------|
| Ollama   | ✅ Required if selected   | llama3, mistral, gemma, phi, etc.  |
| OpenAI   | ✅ Optional               | Requires API key                   |
| LocalHF  | 🔜 Planned                | Hugging Face local models          |

---

## 🧪 Testing

### Running Tests

The project uses pytest for testing. To run tests:

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_profile_meta.py

# Run with verbose output
python -m pytest -v

# Run with coverage report
python -m pytest --cov --cov-config=.coveragerc
```

### Code Coverage

The project includes code coverage reporting in the GitHub Actions CI pipeline. The coverage report is generated using pytest-cov and uploaded to Codecov.

To view the coverage report locally:

```bash
python -m pytest --cov --cov-config=.coveragerc --cov-report=html
```

Then open `coverage_html_report/index.html` in your browser.

### Creating New Tests

1. Create a new file in the `tests` directory with the naming pattern `test_<module_name>.py`
2. Import the module/function to be tested
3. Write test functions that assert expected behavior
4. Use fixtures for common setup/teardown operations

---

## 🧪 Testing the FastAPI API

### 1. Start the API server

From the project root:

```bash
uvicorn engine.api_server:app --reload
```

If `api_keys.json` does not exist, it will be created automatically using:

- The `SUHANA_DEFAULT_API_KEY` from your `.env` file
- Or a secure randomly generated key

---

### 2. Access the interactive Swagger UI

Open in your browser:

```
http://localhost:8000/docs
```

Use the `/query` endpoint, and set the `x-api-key` header.

---

### 3. Example request via `curl`

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY_HERE" \
  -d '{"input": "What is Suhana?", "backend": "ollama"}'
```

---

### 4. Example request via Python

```python
import requests

res = requests.post("http://localhost:8000/query", json={
    "input": "Hello, who are you?",
    "backend": "ollama"
}, headers={
    "x-api-key": "YOUR_API_KEY_HERE"
})

print(res.json())
```

---

### 5. Notes

- API keys are stored in `api_keys.json` (excluded from Git via `.gitignore`)
- To customize the default dev key, define `SUHANA_DEFAULT_API_KEY` in your `.env`
- All keys must be marked `"active": true` to be accepted
- You can edit `api_keys.json` while the server is running — no restart needed


---

## 🛡 License

MIT — use freely, modify locally, and share improvements.

---
