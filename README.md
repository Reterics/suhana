![suhana_right.png](assets/logos/suhana_right.png)

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Self-hosted](https://img.shields.io/badge/self--hosted-yes-brightgreen)]()
[![Powered by](https://img.shields.io/badge/LLM-Ollama%20%7C%20OpenAI-9cf)]()

> Suhana _(수하나)_ is your self-hosted AI companion: a modular chat agent with a personality, local knowledge base, and the ability to run commands — all without giving away your data.

---

## ✨ Features

- 🤖 **Chat with a personality** – Suhana remembers you and responds in character
- 🔍 **Search local knowledge** – markdown, code, and notes in `/knowledge` folder
- 🔄 **Pluggable AI engines** – supports [Ollama](https://ollama.com) (🦙) and OpenAI (🤖)
- 🧠 **Memory-aware** – Suhana evolves with you via `!remember` and `profile.json`
- 🔒 **Self-hosted & portable** – no cloud dependencies, runs on macOS/Windows/Linux
- ⚡ **Execute commands** – define your own actions like `send_message()` or `update_profile()`

---

## 🚀 Quick Start

### 1. Clone the project

```bash
git clone https://github.com/Reterics/suhana.git
cd Suhana
```

### 2. Set up Python environment

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 3. Choose your LLM backend

#### ✅ Option A: [Ollama](https://ollama.com) - local & private

Install Ollama and run one of the supported models:

```bash
ollama run llama3
```
This will download and launch the llama3 model locally.

Other available models include:

- `mistral` – lightweight and fast
- `llama3` – larger and more capable
- `gemma` – Google’s open model
- `phi` – compact and smart
- `codellama` – optimized for coding tasks
- `llava` – for multimodal (image + text) input

You can set the model in `settings.json`:

```json
{
  "llm_backend": "ollama",
  "llm_model": "llama3"
}
```

#### 🤖 Option B: OpenAI – cloud-powered

 1. Create a .env file in the root of the project with your API key:
    ```dotenv
    OPENAI_API_KEY=sk-...
    ```
 2. In settings.json, set your backend and model:
    ```json
    {
      "llm_backend": "openai",
      "llm_model": "gpt-4"
    }
    ```
> Suhana supports both backends. You can switch at runtime using `!switch openai` or `!switch ollama`.

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
| `!remember xyz` | Store user facts in `profile.json`      |
| `!exit`         | Leave the session                       |

---

## 🧩 Folder Structure

```
Suhana/
├─ engine/         # Core agent logic
├─ knowledge/      # Your documents and notes
├─ vectorstore/    # Local FAISS index (auto-generated)
├─ models/         # Persona config (`persona.yaml`)
├─ profile.json    # User memory and preferences
├─ settings.json   # Backend + model config
├─ ingest.py       # File indexer
└─ main.py         # Entry point
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

| Engine   | Status     | Notes                     |
|----------|------------|---------------------------|
| Ollama   | ✅ Stable   | llama3, mistral, etc.     |
| OpenAI   | ✅ Optional | Requires API key          |
| LocalHF  | 🔜 Planned  | Hugging Face local models |

---

## 🛡 License

MIT — use freely, modify locally, and share improvements.

---
