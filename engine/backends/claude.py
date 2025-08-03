from anthropic import Anthropic
from engine.history import trim_message_history
from engine.backends.error_handling import handle_backend_errors, handle_streaming_errors

CLAUDE_SUMMARY_PROMPT = "Summarize the following conversation briefly."

def summarize_history_claude(messages, client, model):
    """
    Summarize conversation history using Claude API.

    Args:
        messages: List of message dictionaries
        client: Anthropic client instance
        model: Claude model name

    Returns:
        Summary of the conversation
    """
    summary_prompt = [
        {"role": "user", "content": CLAUDE_SUMMARY_PROMPT},
    ] + messages
    # Claude's API expects a specific message structure
    response = client.messages.create(
        model=model,
        messages=summary_prompt,
        max_tokens=200,
        temperature=0.3,
    )
    # Claude SDK: response.content is a list of content blocks (usually one)
    if response.content:
        return response.content[0].text.strip()
    return ""

@handle_backend_errors("Claude")
def query_claude(prompt, system_prompt, profile, settings, force_stream):
    """
    Query the Claude API with the given prompt.

    Args:
        prompt: User input
        system_prompt: System instructions
        profile: User profile with conversation history
        settings: Application settings
        force_stream: Whether to force streaming mode

    Returns:
        Response from Claude or a generator for streaming responses
    """
    api_key = settings.get("claude_api_key")
    if not api_key:
        return "[❌ Claude API key not set. Please define it in settings.json or as an env var.]"
    model = settings.get("claude_model", "claude-3-opus-20240229")
    client = Anthropic(api_key=api_key)
    stream = settings.get("streaming", False)
    if force_stream:
        stream = True

    old, recent = profile["history"][:-20], profile["history"][-20:]
    recent.append({"role": "user", "content": prompt})

    if old:
        summary = summarize_history_claude(old, client, model)
        msgs = [{"role": "system", "content": f"Summary of earlier conversation: {summary}"}] + recent
    else:
        msgs = [{"role": "system", "content": system_prompt}] + recent

    trimmed = trim_message_history(msgs, model=model)
    # Claude uses a list of dicts for messages
    messages = trimmed

    if stream:
        # Streaming: yields text as tokens arrive
        def stream_generator():
            stream_reply = ""
            response_stream = client.messages.create(
                model=model,
                messages=messages,
                max_tokens=1024,
                temperature=0.7,
                stream=True
            )
            for event in response_stream:
                # Each event.content_block_delta.text is a chunk
                token = getattr(event, "content_block_delta", None)
                token_text = token.text if token else ""
                stream_reply += token_text
                yield token_text
            profile["history"].extend([
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": stream_reply}
            ])

        # Wrap the generator with error handling
        return handle_streaming_errors("Claude", stream_generator)()
    else:
        response = client.messages.create(
            model=model,
            messages=messages,
            max_tokens=1024,
            temperature=0.7
        )
        if response.content:
            reply = response.content[0].text.strip()
        else:
            reply = ""
        profile["history"].extend([
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": reply}
        ])
        return reply
