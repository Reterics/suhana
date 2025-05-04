from engine.engine_config import load_settings, switch_backend
from engine.profile import load_profile
from engine.agent_core import handle_input

def run_agent():
    settings = load_settings()
    backend = settings.get("llm_backend", "ollama")
    profile = load_profile()
    name = "Suhana"

    print(f"Hello, I'm {name} — {'🦙' if backend == 'ollama' else '🤖'} ({settings.get('llm_model') if backend == 'ollama' else settings.get('openai_model')})\n")

    while True:
        try:
            user_input = input("> ").strip()
            if user_input.lower() in ("exit", "quit"):
                print("Goodbye.")
                break

            if user_input.startswith("!"):
                # handle_command(user_input[1:].strip())
                continue

            if user_input.startswith("switch "):
                backend = switch_backend(user_input.split(" ")[1], settings)
                continue
            elif user_input == "engine":
                print(f"🔧 Current engine: {'🦙' if backend == 'ollama' else '🤖'} {backend.upper()} ({settings.get('llm_model') if backend == 'ollama' else settings.get('openai_model')})")
                continue

            print("[LLM] Thinking...")
            response = handle_input(user_input, backend, profile, settings, name)
            print(f"{name}: {response}\n")

        except KeyboardInterrupt:
            print("\nSession ended.")
            break
