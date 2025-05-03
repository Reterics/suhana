# ✅ Suhana AI - Core TODO List

This checklist tracks the next major steps after initial scaffolding.
Platform notes are included for **Windows** and **macOS** where relevant.

---

## ✅ 1. Install Ollama and Run a Local Model

**Install Ollama** on your system:
- macOS:  
  ```bash
  brew install ollama
  ```
- Windows (via installer):  
  Download and install from: https://ollama.com/download

**Start a local model:**
```bash
ollama run llama3
```

Verify that the Ollama server runs at `http://localhost:11434`.

---

## ✅ 2. Add Ollama to `engine/agent.py`

Replace the mock LLM call with a real one using `requests`:

```python
import requests

def query_ollama(prompt, model="llama3"):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": False}
    )
    return response.json()["response"].strip()
```

Then, in `run_agent()`, replace the mock response with:

```python
response = query_ollama(prompt)
print(f"{config['name']}: {response}\n")
```

---

## ✅ 3. Add Dependency to `requirements.txt`

```txt
requests
```

Install with:
```bash
pip install -r requirements.txt
```

---

## ✅ 4. (Optional) Add `.env` or `settings.json`

Create `settings.json` for engine selection:

```json
{
  "llm_model": "llama3",
  "embedding_model": "all-MiniLM-L6-v2"
}
```

Load it in `agent.py`:

```python
with open("settings.json", "r", encoding="utf-8") as f:
    settings = json.load(f)
model_name = settings.get("llm_model", "llama3")
```

---

## ✅ 5. Test Workflow

```bash
# Rebuild vector index after adding new files
python ingest.py

# Start the agent
python main.py
```

Example:
```
> What is in notes about the Azure pipeline?
Suhana: [response based on knowledge search + Ollama]
```

---

## ✅ 6. (Optional) Add GPU config (advanced)

On supported devices, Ollama will auto-detect GPU (M1/M2 or CUDA).  
You can optimize startup with:

```bash
ollama run llama3:latest --gpu
```

For Windows with NVIDIA GPU:
- Ensure WSL2 is installed + Ollama installed inside WSL
- Enable GPU support inside WSL via `nvidia-smi`

For Windows with [AMD](https://ollama.com/blog/amd-preview) GPU:
```bash
ollama run llama3:latest
```

---

## ✅ 7. Next Ideas

- Add support for switching between Ollama and OpenAI or Hugging Face
- Allow persona + engine switching via CLI flag
- Auto-ingest files when changed
- Add TUI with `rich` or `textual`
- Log all responses to a JSONL transcript
- Enable voice mode (Whisper ASR + TTS)

---

📁 Save this checklist in your repo as `TODO.md` or paste it to me later for continuation.
