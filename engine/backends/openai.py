from openai import OpenAI
from engine.history import trim_message_history
from engine.backends.error_handling import handle_backend_errors, handle_streaming_errors

def summarize_history(messages, client, model):
    """
    Summarize conversation history using OpenAI API.

    Args:
        messages: List of message dictionaries
        client: OpenAI client instance
        model: OpenAI model name

    Returns:
        Summary of the conversation
    """
    summary_prompt = [{"role": "system", "content": "Summarize the following conversation briefly."}] + messages
    response = client.chat.completions.create(model=model, messages=summary_prompt, max_tokens=200, temperature=0.3)
    return response.choices[0].message.content.strip()

@handle_backend_errors("OpenAI")
def query_openai(prompt, system_prompt, profile, settings, force_stream):
    """
    Query the OpenAI API with the given prompt.

    Args:
        prompt: User input
        system_prompt: System instructions
        profile: User profile with conversation history
        settings: Application settings
        force_stream: Whether to force streaming mode

    Returns:
        Response from OpenAI or a generator for streaming responses
    """
    api_key = settings.get("openai_api_key")
    if not api_key:
        return "[❌ OpenAI API key not set. Please define it in settings.json or as an env var.]"
    client = OpenAI(api_key=api_key)
    model = settings["openai_model"]
    stream = settings.get("streaming", False)
    if force_stream:
        stream = True

    # Add user message to history immediately
    profile["history"].append({"role": "user", "content": prompt})

    # Split history for context building
    old, recent = profile["history"][:-20], profile["history"][-20:]

    if old:
        summary = summarize_history(old, client, model)
        msgs = [{"role": "system", "content": f"Summary of earlier conversation: {summary}"}] + recent
    else:
        msgs = [{"role": "system", "content": system_prompt}] + recent

    trimmed = trim_message_history(msgs, model=model)
    if stream:
        response = client.chat.completions.create(model=model, messages=trimmed, stream=True)

        def stream_generator():
            stream_reply = ""
            for chunk in response:
                token = chunk.choices[0].delta.content or ""
                stream_reply += token
                yield token
            # Only add assistant's reply since user's message was already added
            profile["history"].append({"role": "assistant", "content": stream_reply})

        # Wrap the generator with error handling
        return handle_streaming_errors("OpenAI", stream_generator)()
    else:
        response = client.chat.completions.create(model=model, messages=trimmed, temperature=0.7)
        reply = response.choices[0].message.content.strip()
        # Only add assistant's reply since user's message was already added
        profile["history"].append({"role": "assistant", "content": reply})
        return reply
