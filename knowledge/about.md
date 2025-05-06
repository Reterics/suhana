# Suhana AI Agent

**Suhana** is a modular, self-hosted AI chat agent with a persistent persona and file-based knowledge base. It can converse naturally with users, perform actions, search local documents, and be extended with new tools or models — all while keeping costs low and ownership in your hands.

---

## 📚 Table of Contents

1. [Overview](#overview)  
2. [Core Features](#core-features)  
3. [Architecture](#architecture)  
4. [Technology Stack](#technology-stack)  
5. [Folder Structure](#folder-structure)  
6. [Agent Behavior](#agent-behavior)  
7. [Knowledge Base Management](#knowledge-base-management)  
8. [Command Execution](#command-execution)  
9. [Modularity & Engine Switching](#modularity--engine-switching)  
10. [Deployment & Portability](#deployment--portability)  
11. [Future Ideas](#future-ideas)

---

## 1. Overview

Suhana is a character-driven AI agent capable of general conversation, task execution, and information retrieval from a local or remote knowledge base. It is designed to be self-hosted, extendable, and free from reliance on proprietary APIs.

---

## 2. Core Features

- Conversational AI with a persistent **persona** ("Suhana")  
- File-based **knowledge base** (markdown, text, code, etc.)  
- Built-in **command execution** layer (send messages, update files, modify user profile)  
- Supports **tool use** (e.g. web search or calling APIs)  
- Swappable **AI engines** (LLaMA 3, Mistral, GPT, etc.)  
- Works **offline** or optionally connects to the web  
- **Low-cost or free** to run, portable across environments

---

## 3. Architecture

```
User ─▶ Suhana Engine ─▶ [ Knowledge Retriever ]
                         ├▶ [ Action Executor ]
                         └▶ [ Persona Memory + Profile ]
```

Core logic is handled by a control loop using reasoning + acting + memory updates (ReAct-like).

---

## 4. Technology Stack

| Layer              | Tools / Libraries                           |
|-------------------|----------------------------------------------|
| AI Engine          | Ollama + LLaMA3 / Mistral (pluggable)       |
| Embeddings         | `sentence-transformers` (e.g., all-MiniLM)  |
| Vector Store       | FAISS or ChromaDB                           |
| Retrieval Logic    | Custom RAG controller or LangChain          |
| Command Layer      | Python plugins or YAML-mapped actions       |
| Storage            | Files, JSON, Markdown                       |
| Interface          | CLI (TUI planned), optional web shell       |

---

## 5. Folder Structure

```
 Suhana/
 ├─ engine/         # Main loop, tools, agents
 │  ├─ agent.py             # CLI loop entrypoint
 │  ├─ agent_core.py        # handle_input
 │  ├─ api_key_store.py     # API Key management
 │  ├─ api_server.py        # FastAPI server
 │  ├─ engine_config.py     # Model backend config & switching
 │  ├─ profile.py           # Profile memory & summarization
 │  ├─ history.py           # Message trimming and summarization
 │  ├─ voice.py             # Coqui TTS and Whisper implementation
 │  └─ backends/            # Backend-specific logic (Ollama/OpenAI)
 │     ├─ ollama.py
 │     └─ openai.py
 ├─ models/         # Prompt templates, system prompts
 ├─ knowledge/      # Docs, code, notes to ingest
 ├─ vectorstore/    # Index for semantic search
 ├─ actions/        # Executable commands (e.g., Python)
 ├─ profile.json    # User memory, preferences
 └─ main.py         # Entrypoint to run the agent
```

---

## 6. Agent Behavior

- Starts a conversation loop with the user  
- Maintains persona and context  
- Uses embeddings to search indexed knowledge base  
- Can optionally query the internet  
- Executes registered commands if requested

---

## 7. Knowledge Base Management

- Drop `.txt`, `.md`, `.pdf`, or code files into `/knowledge`  
- Use `ingest.py` (or auto-ingestion) to re-index  
- Uses vector search to retrieve relevant chunks during conversation

---

## 8. Command Execution

Commands are registered as:
- Python functions  
- Shell or HTTP hooks  
- YAML-defined triggers with parameters  

Example:
```python
def send_message(destination, content):
    # POST to API or write to file
    pass
```

---

## 9. Modularity & Engine Switching

AI models can be:
- Run locally via **Ollama**  
- Configured per session in `settings.json`  
- Swapped easily for future upgrade (e.g. LLaVA, Gemma, Mixtral)

---

## 10. Deployment & Portability

- Entire project runs locally  
- Easy to Dockerize for remote/server use  
- No dependency on cloud APIs  
- Can run on any machine with Python + CPU/GPU

---

## 11. Future Ideas

- GUI with Next.js or Electron  
- Fine-tuned persona or memory vector store  
- Multi-agent mode or background daemon  
- Voice input/output support (Whisper, Coqui)  
- Secure API for third-party integration

---
