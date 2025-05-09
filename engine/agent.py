from engine.action_store import execute_action
from engine.engine_config import load_settings, switch_backend
from engine.agent_core import handle_input
from engine.voice import transcribe_audio, speak_text
from engine.memory_store import add_memory_fact, recall_memory, forget_memory
from engine.intent import detect_intent
from engine.conversation_store import (
    create_new_conversation,
    load_conversation,
    save_conversation, list_conversations, list_conversation_meta
)

def run_agent():
    settings = load_settings()
    backend = settings.get("llm_backend", "ollama")
    voice_mode = settings.get("voice", False)
    stream = settings.get("streaming", False)
    conversation_id = create_new_conversation()
    profile = load_conversation(conversation_id)
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
            if command in ("exit", "quit"):
                print("Goodbye.")
                break
            if command == "voice on":
                voice_mode = True
                print("🎙️ Voice mode enabled.")
                continue
            if command == "voice off":
                voice_mode = False
                print("🛑 Voice mode disabled.")
                continue
            if command == "!load":
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
            if command.startswith("switch "):
                backend = switch_backend(command.split(" ")[1], settings)
                continue
            elif command == "engine":
                print(
                    f"🔧 Current engine: {'🦙' if backend == 'ollama' else '🤖'} {backend.upper()} ({settings.get('llm_model') if backend == 'ollama' else settings.get('openai_model')})")
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

            intent_data = detect_intent(user_input)
            if intent_data["intent"]:
                print(f"[🔎] Detected intent: {intent_data['intent']} → {intent_data['params']}")
                result = execute_action(intent_data["action"], intent_data["params"], intent_data)
                print(f"{name}: {result}\n")
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
