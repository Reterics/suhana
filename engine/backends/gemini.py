import google.generativeai as genai
from engine.history import trim_message_history
from engine.backends.error_handling import handle_backend_errors, handle_streaming_errors

GEMINI_SUMMARY_PROMPT = "Summarize the following conversation briefly:"

def _setup_genai(api_key):
    """
    Configure the Gemini API with the provided API key.

    Args:
        api_key: Gemini API key
    """
    genai.configure(api_key=api_key)

def summarize_history_gemini(messages, api_key, model):
    """
    Summarize conversation history using Gemini API.

    Args:
        messages: List of message dictionaries
        api_key: Gemini API key
        model: Gemini model name

    Returns:
        Summary of the conversation
    """
    _setup_genai(api_key)
    flat = ""
    for msg in messages:
        role = msg["role"]
        flat += f"{'User' if role == 'user' else 'Assistant'}: {msg['content']}\n"
    prompt = f"{GEMINI_SUMMARY_PROMPT}\n\n{flat}\n\nSummary:"

    model_obj = genai.GenerativeModel(model)
    # Use single-shot completion for summary
    response = model_obj.generate_content(prompt)
    return response.text.strip()

@handle_backend_errors("Gemini")
def query_gemini(prompt, system_prompt, profile, settings, force_stream):
    """
    Query the Gemini API with the given prompt.

    Args:
        prompt: User input
        system_prompt: System instructions
        profile: User profile with conversation history
        settings: Application settings
        force_stream: Whether to force streaming mode

    Returns:
        Response from Gemini or a generator for streaming responses
    """
    api_key = settings.get("gemini_api_key")
    if not api_key:
        return "[❌ Gemini API key not set. Please define it in settings.json or as an env var.]"
    model = settings.get("gemini_model", "gemini-pro")
    stream = settings.get("streaming", False)
    if force_stream:
        stream = True

    _setup_genai(api_key)
    model_obj = genai.GenerativeModel(model)

    # Add user message to history immediately
    profile["history"].append({"role": "user", "content": prompt})

    # Split history for context building
    old, recent = profile["history"][:-20], profile["history"][-20:]

    if old:
        summary = summarize_history_gemini(old, api_key, model)
        msgs = [{"role": "system", "content": f"Summary of earlier conversation: {summary}"}] + recent
    else:
        msgs = [{"role": "system", "content": system_prompt}] + recent

    trimmed = trim_message_history(msgs, model=model)
    # Convert messages to Gemini prompt format
    text = "\n".join([f"{m['role'].capitalize() if m['role'] != 'system' else ''}: {m['content']}" for m in trimmed])
    text += f"\nUser: {prompt}\nAssistant:"

    if stream:
        def stream_generator():
            stream_reply = ""
            # SDK streaming generator
            response_stream = model_obj.generate_content(text, stream=True)
            for chunk in response_stream:
                token = chunk.text
                stream_reply += token
                yield token
            # Only add assistant's reply since user's message was already added
            profile["history"].append({"role": "assistant", "content": stream_reply})

        # Wrap the generator with error handling
        return handle_streaming_errors("Gemini", stream_generator)()
    else:
        response = model_obj.generate_content(text)
        reply = response.text.strip()
        # Only add assistant's reply since user's message was already added
        profile["history"].append({"role": "assistant", "content": reply})
        return reply
