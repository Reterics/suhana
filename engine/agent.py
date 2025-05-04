def run_agent():
    from engine.engine_config import load_settings, switch_backend
    from engine.profile import load_profile, save_profile, summarize_profile_for_prompt
    from engine.history import trim_message_history
    from engine.backends.ollama import query_ollama
    from engine.backends.openai import query_openai
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS

    settings = load_settings()
    backend = settings.get("llm_backend", "ollama")
    profile = load_profile()

    name = "Suhana"
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2", model_kwargs={'trust_remote_code': True})
    docsearch = FAISS.load_local("vectorstore", embedding_model, allow_dangerous_deserialization=True)

    print(f"Hello, I'm {name} — {'🦙' if backend == 'ollama' else '🤖'} ({settings.get('llm_model') if backend == 'ollama' else settings.get('openai_model')})\n")

    while True:
        try:
            user_input = input("> ").strip()
            command = user_input[1:].strip()

            if user_input.lower() in ("exit", "quit"):
                print("Goodbye.")
                break

            if command.startswith("switch "):
                backend = switch_backend(command.split(" ")[1], settings)
                continue
            elif command == "engine":
                print(f"🔧 Current engine: {'🦙' if backend == 'ollama' else '🤖'} {backend.upper()} ({settings.get('llm_model') if backend == 'ollama' else settings.get('openai_model')})")
                continue

            if user_input.startswith("!"):
                # handle_command(command)
                continue

            docs = docsearch.similarity_search(user_input, k=3)
            context = "\n".join([d.page_content for d in docs])
            system_prompt = f"{summarize_profile_for_prompt(profile)}\nContext: {context}"

            print("[LLM] Thinking...")
            if backend == "ollama":
                response = query_ollama(user_input, system_prompt, profile, settings)
            elif backend == "openai":
                response = query_openai(user_input, system_prompt, profile, settings)
            else:
                response = "[❌ Unknown backend]"
            print(f"{name}: {response}\n")

            save_profile(profile)

        except KeyboardInterrupt:
            print("\nSession ended.")
            break