from openai import OpenAI
from engine.history import trim_message_history

def summarize_history(messages, client, model):
    summary_prompt = [{"role": "system", "content": "Summarize the following conversation briefly."}] + messages
    response = client.chat.completions.create(model=model, messages=summary_prompt, max_tokens=200, temperature=0.3)
    return response.choices[0].message.content.strip()

def query_openai(prompt, system_prompt, profile, settings, force_stream):
    api_key = settings.get("openai_api_key")
    if not api_key:
        return "[❌ OpenAI API key not set. Please define it in settings.json or as an env var.]"
    client = OpenAI(api_key=api_key)
    model = settings["openai_model"]
    stream = settings.get("streaming", False)
    if force_stream:
        stream = True

    old, recent = profile["history"][:-20], profile["history"][-20:]
    recent.append({"role": "user", "content": prompt})

    if old:
        summary = summarize_history(old, client, model)
        msgs = [{"role": "system", "content": f"Summary of earlier conversation: {summary}"}] + recent
    else:
        msgs = [{"role": "system", "content": system_prompt}] + recent

    trimmed = trim_message_history(msgs, model=model)
    if stream:
        response = client.chat.completions.create(model=model, messages=trimmed, stream=True)

        def gen():
            stream_reply = ""
            for chunk in response:
                token = chunk.choices[0].delta.content or ""
                stream_reply += token
                yield token
            profile["history"].extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": stream_reply}])

        return gen()
    else:
        response = client.chat.completions.create(model=model, messages=trimmed, temperature=0.7)
        reply = response.choices[0].message.content.strip()
        profile["history"].extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}])
        return reply
