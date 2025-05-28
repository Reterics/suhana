import subprocess

from engine.engine_config import load_settings, switch_backend
from engine.agent_core import (handle_input, vectorstore_manager)
from engine.tool_store import load_tools, match_and_run_tools
from engine.voice import transcribe_audio, speak_text
from engine.memory_store import add_memory_fact, recall_memory, forget_memory
from engine.conversation_store import (
    create_new_conversation,
    load_conversation,
    save_conversation, list_conversation_meta
)

def run_agent():
    settings = load_settings()
    backend = settings.get("llm_backend", "ollama")
    voice_mode = settings.get("voice", False)
    stream = settings.get("streaming", False)
    conversation_id = create_new_conversation()
    profile = load_conversation(conversation_id)
    tools = load_tools()
    name = "Suhana"

    print(f"Hello, I'm {name} — {'🦙' if backend == 'ollama' else '🤖'} ({settings.get('llm_model') if backend == 'ollama' else settings.get('openai_model')})\n")
    print("Type 'voice on' to enable voice input/output, 'voice off' to disable.\n")

    while True:
        try:
            user_input = transcribe_audio() if voice_mode else input("> ").strip()
            if voice_mode:
                print(f"You: {user_input}")
            command = user_input.lower().strip()

            if not user_input.strip():
                continue
            elif command in ("exit", "quit"):
                print("Goodbye.")
                break
            elif command == "voice on":
                voice_mode = True
                print("🎙️ Voice mode enabled.")
                continue
            elif command == "voice off":
                voice_mode = False
                print("🛑 Voice mode disabled.")
                continue
            elif command == "!load":
                conversations = list_conversation_meta()
                print("📜 Available conversations:")
                for i, meta in enumerate(conversations):
                    print(f"{i + 1}. [{meta['title']}] – {meta['last_updated']}")
                choice = input("Enter number to load: ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(conversations):
                    conversation_id = conversations[int(choice) - 1]['id']
                    profile = load_conversation(conversation_id)
                    print(f"✅ Switched to conversation: {conversation_id}")
                else:
                    print("❌ Invalid selection.")
                continue
            elif command.startswith("switch "):
                backend = switch_backend(command.split(" ")[1], settings)
                continue
            elif command == "engine":
                print(
                    f"🔧 Current engine: {'🦙' if backend == 'ollama' else '🤖'} {backend.upper()} ({settings.get('llm_model') if backend == 'ollama' else settings.get('openai_model')})")
                continue
            elif command.startswith("!mode "):
                profile["mode"] = command.split(" ", 1)[1].strip()
                print(f"🔧 Mode set to: {profile['mode']}")
                if profile["mode"] != vectorstore_manager.current_vector_mode:
                    vectorstore_manager.get_vectorstore(profile)
                continue
            elif command.startswith("!project "):
                profile["project_path"] = command.split(" ", 1)[1].strip()
                profile["mode"] = "development"
                print(f"📂 Project set to: {profile['project_path']}")
                # Load the development vectorstore
                vectorstore_manager.get_vectorstore(profile)
                continue
            elif command == "!reindex":
                path = profile.get("project_path")
                if path:
                    subprocess.run(["python", "ingest_project.py", path])
                    # Reset the vectorstore to force reloading
                    vectorstore_manager.vectorstore = None
                    vectorstore_manager.get_vectorstore(profile)
                    print("✅ Vectorstore reloaded.")
                else:
                    print("⚠️ Set project path first with !project")
                continue
            if user_input.startswith("!remember "):
                fact = user_input[len("!remember "):]
                add_memory_fact(fact)
                print(f"🧠 Remembered: {fact}\n")
                continue
            if user_input.strip() == "!recall":
                facts = recall_memory()
                if not facts:
                    print("🧠 No memories stored.\n")
                else:
                    print("🧠 Memories:\n" + "\n".join(f"- {fact}" for fact in facts) + "\n")
                continue
            if user_input.startswith("!forget "):
                keyword = user_input[len("!forget "):].strip()
                removed = forget_memory(keyword)
                print(f"🧹 Removed {removed} memory entry(ies) matching '{keyword}'.\n")
                continue

            action_data = match_and_run_tools(user_input, tools)
            if action_data is not None:
                print(f"{name}: {action_data}\n")
                continue

            print("🎙️ Thinking...")
            response = handle_input(user_input, backend, profile, settings)
            if stream:
                print(f"{name}: ", end="", flush=True)
                reply = ""
                for token in response:
                    print(token, end="", flush=True)
                    reply += token
                print("\n")
            else:
                print(f"{name}: {response}\n")

            save_conversation(conversation_id, profile)
            if voice_mode:
                speak_text(response)

        except KeyboardInterrupt:
            print("\nSession ended.")
            break
