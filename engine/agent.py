import json
import os

import openai
import requests
import yaml
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv
from openai.types.chat import ChatCompletionMessageParam

load_dotenv()

# from engine.actions import handle_command

name = 'Suhana'

# Load settings for model
with open("settings.json", "r", encoding="utf-8") as f:
    settings = json.load(f)
backend = settings.get("llm_backend", "ollama")
ollama_model = settings.get("llm_model", "llama3")
openai_model = settings.get("openai_model", "gpt-3.5-turbo")
openai.api_key = settings.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
client = None
if openai.api_key:
    from openai import OpenAI
    client = OpenAI(api_key=openai.api_key)


def query_ollama(prompt, system_prompt):
    global profile

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": ollama_model, "prompt": f"{system_prompt}\n\nUser: {prompt}\n{name}:", "stream": False}
    )
    return response.json()["response"].strip()

def query_openai(prompt, system_prompt):
    global profile
    if not client:
        return "[❌ OpenAI API key not provided. Please set OPENAI_API_KEY or define it in settings.json] or switch back to ollama"

    messages: list[ChatCompletionMessageParam] = [ # type: ignore
        {"role": "system", "content": system_prompt },  # ← Suhana's setup
        {"role": "user", "content": prompt}
    ]

    response = client.chat.completions.create(
        model=openai_model,
        messages=messages,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

PROFILE_PATH = "profile.json"

# Default structure
default_profile = {
    "name": "User",
    "history": [],
    "preferences": {
        "preferred_language": "English",
        "communication_style": "neutral",
        "focus": "general"
    },
    "memory": []
}

if os.path.exists(PROFILE_PATH):
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        profile = json.load(f)
else:
    profile = default_profile


def summarize_profile_for_prompt() -> str:
    global profile
    preferences = profile.get("preferences", {})
    memory = profile.get("memory", [])

    summary = f"You are Suhana, You are speaking to {profile.get('name', 'User')}.\n"
    summary += "Preferences:\n"
    summary += "\n".join([f"- {k.replace('_', ' ').capitalize()}: {v}" for k, v in preferences.items()]) or "None"

    if memory:
        summary += "\nKnown facts:\n"
        summary += "\n".join([f"- {item['content']}" for item in memory])
    return summary

# Load embedding model
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2", model_kwargs = {'trust_remote_code': True})
docsearch = FAISS.load_local("vectorstore", embedding_model, allow_dangerous_deserialization=True)


def run_agent():
    global backend
    engine_icon = "🦙" if backend == "ollama" else "🤖"
    model = ollama_model if backend == "ollama" else openai_model
    print(f"Hello, I'm {name} — {engine_icon} ({model})\n")

    while True:
        try:
            user_input = input("> ").strip()
            command = user_input[1:].strip()

            if user_input.lower() in ("exit", "quit"):
                print("Goodbye.")
                break

            if command.startswith("switch "):
                new_backend = command.split(" ")[1]
                if new_backend in ["ollama", "openai"]:
                    settings["llm_backend"] = new_backend
                    backend = new_backend
                    with open("settings.json", "w", encoding="utf-8") as f:
                        json.dump(settings, f, indent=2)
                    print(f"🔁 Switched to {new_backend.upper()}")
                else:
                    print("❌ Supported engines: ollama, openai")
                continue
            elif command == "engine":
                model = ollama_model if backend == "ollama" else openai_model
                icon = "🦙" if backend == "ollama" else "🤖"
                print(f"🔧 Current engine: {icon} {backend.upper()} ({model})")
                continue


            if user_input.startswith("!"):
                #handle_command(user_input[1:]) # See: Roadmap
                continue

            # Search knowledge base
            docs = docsearch.similarity_search(user_input, k=3)
            context = "\n".join([d.page_content for d in docs])
            system_prompt = f"{summarize_profile_for_prompt()}\nContext: {context}"

            print("[LLM] Thinking...")
            # Get response from selected backend
            if backend == "ollama":
                response = query_ollama(user_input, system_prompt)
            elif backend == "openai":
                response = query_openai(user_input, system_prompt)
            else:
                response = "[❌ Unknown backend]"
            print(f"{name}: {response}\n")
        except KeyboardInterrupt:
            print("\nSession ended.")
            break
