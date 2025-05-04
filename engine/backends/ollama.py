import requests
from engine.history import trim_message_history

def summarize_history_offline(messages, model):
    flat = ""
    for msg in messages:
        role = msg["role"]
        flat += f"{'User' if role == 'user' else 'Suhana'}: {msg['content']}\n"

    prompt = f"Summarize the following conversation briefly:\n\n{flat}\n\nSummary:"
    resp = requests.post("http://localhost:11434/api/generate", json={"model": model, "prompt": prompt, "stream": False})
    return resp.json()["response"].strip()

def query_ollama(prompt, system_prompt, profile, settings):
    model = settings["llm_model"]
    old, recent = profile["history"][:-20], profile["history"][-20:]
    recent.append({"role": "user", "content": prompt})

    if old:
        summary = summarize_history_offline(old, model)
        msgs = [{"role": "system", "content": f"Summary of earlier conversation: {summary}"}] + recent
    else:
        msgs = [{"role": "system", "content": system_prompt}] + recent

    trimmed = trim_message_history(msgs, model="gpt-3.5-turbo")
    text = "\n".join([f"{m['role'].capitalize() if m['role'] != 'system' else ''}: {m['content']}" for m in trimmed])
    text += f"\nUser: {prompt}\nSuhana:"

    resp = requests.post("http://localhost:11434/api/generate", json={"model": model, "prompt": text, "stream": False})
    reply = resp.json()["response"].strip()

    profile["history"].extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}])
    return reply
