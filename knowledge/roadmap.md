# 🗺️ Suhana Development Roadmap

### ✅ Completed
- **CLI Core Loop**  
  `agent.py` with modular backend support (`ollama`, `openai`)
- **Voice Mode**  
  Whisper STT + Coqui TTS, runtime toggle (`voice.py`)
- **Knowledge Base Search (RAG)**  
  `ingest.py`, `FAISS`, `sentence-transformers`
- **Profile & Memory**  
  Persistent `profile.json`, summarization, persona preferences
- **FastAPI Server**  
  REST API with key-based auth + CORS (`api_server.py`)

---

### 🚧 Planned

## 1. 🖥️ Web-based GUI (Frontend Shell)
- Minimal browser UI to chat with Suhana
- Support both typed input and microphone (WebRTC or MediaRecorder)
- Uses FastAPI `/query` endpoint with API key

## 2. 🧠 Dynamic Memory Storage
- Store memory entries (facts, interactions) into a second vectorstore (`/memory`)
- Alternatively: use `/knowledge` for both static + dynamic by tagging
- Add `!remember`, `!forget`, `!recall` support later

## 3. 🛠️ Tool Use & Intent Detection
- Register callable tools Suhana can invoke via prompt
- Intent → function mapping (rule-based or LLM classifier)
- Example: “What’s the weather?” → `weather()` function
- Structure for registering tools with metadata (type, trigger)

## 4. 🧾 Command Execution Layer
- Create `handle_command` dispatcher in `agent.py`
- Add `actions/` folder with Python/YAML-defined commands
- Built-in commands: `!note`, `!run`, `!send`, `!update_profile`

## 5. 🐳 Dockerization & Deployment
- `Dockerfile`, `.env`, `docker-compose.yml`
- Volume-mount folders like `/knowledge`, `/vectorstore`
- GPU/CPU toggle and backend engine env config

---

### 📌 Optional Future Features
- GUI app (Electron / Tauri)
- Background daemon + tray support
- Multi-agent support
- Remote control via Telegram, Matrix, etc.
