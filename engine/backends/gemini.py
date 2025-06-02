import google.generativeai as genai
from engine.history import trim_message_history

GEMINI_SUMMARY_PROMPT = "Summarize the following conversation briefly:"

def _setup_genai(api_key):
    genai.configure(api_key=api_key)

def summarize_history_gemini(messages, api_key, model):
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

def query_gemini(prompt, system_prompt, profile, settings, force_stream):
    api_key = settings.get("gemini_api_key")
    if not api_key:
        return "[❌ Gemini API key not set. Please define it in settings.json or as an env var.]"
    model = settings.get("gemini_model", "gemini-pro")
    stream = settings.get("streaming", False)
    if force_stream:
        stream = True

    _setup_genai(api_key)
    model_obj = genai.GenerativeModel(model)

    old, recent = profile["history"][:-20], profile["history"][-20:]
    recent.append({"role": "user", "content": prompt})

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
        def gen():
            stream_reply = ""
            try:
                # SDK streaming generator
                response_stream = model_obj.generate_content(text, stream=True)
                for chunk in response_stream:
                    token = chunk.text
                    stream_reply += token
                    yield token
            except Exception:
                error_msg = "[Gemini connection error]"
                stream_reply += error_msg
                yield error_msg
            profile["history"].extend([
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": stream_reply}
            ])
        return gen()
    else:
        try:
            response = model_obj.generate_content(text)
            reply = response.text.strip()
        except Exception:
            reply = "[Gemini connection error]"
        profile["history"].extend([
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": reply}
        ])
        return reply
