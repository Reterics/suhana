import requests
import json
from engine.history import trim_message_history
from engine.backends.error_handling import handle_backend_errors, handle_streaming_errors

def summarize_history_offline(messages, model):
    """
    Summarize conversation history using Ollama API.

    Args:
        messages: List of message dictionaries
        model: Ollama model name

    Returns:
        Summary of the conversation
    """
    flat = ""
    for msg in messages:
        role = msg["role"]
        flat += f"{'User' if role == 'user' else 'Suhana'}: {msg['content']}\n"

    prompt = f"Summarize the following conversation briefly:\n\n{flat}\n\nSummary:"
    resp = requests.post("http://localhost:11434/api/generate", json={"model": model, "prompt": prompt, "stream": False})
    return resp.json()["response"].strip()


def get_downloaded_models():
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return [model["name"] for model in models]
    except requests.RequestException as e:
        print("Failed to get models:", e)
        return [
            "llama3",
            "llama2",
            "mistral",
            "codellama",
            "phi",
            "gemma"
        ]

@handle_backend_errors("Ollama")
def query_ollama(prompt, system_prompt, profile, settings, force_stream):
    """
    Query the Ollama API with the given prompt.

    Args:
        prompt: User input
        system_prompt: System instructions
        profile: User profile with conversation history
        settings: Application settings
        force_stream: Whether to force streaming mode

    Returns:
        Response from Ollama or a generator for streaming responses
    """
    model = settings["llm_model"]
    stream = settings.get("streaming", False)
    if force_stream:
        stream = True

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

    if stream:
        def stream_generator():
            stream_reply = ""
            with requests.post("http://localhost:11434/api/generate",
                               json={"model": model, "prompt": text, "stream": True}, stream=True) as resp:
                resp.raise_for_status()  # Raises an exception for 4xx/5xx errors
                for line in resp.iter_lines():
                    if line:
                        data = json.loads(line)
                        token = data.get("response", "")
                        stream_reply += token
                        yield token
            profile["history"].extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": stream_reply}])

        # Wrap the generator with error handling
        return handle_streaming_errors("Ollama", stream_generator)()
    else:
        resp = requests.post("http://localhost:11434/api/generate", json={"model": model, "prompt": text, "stream": False})
        if resp.status_code == 404:
            models_list = get_downloaded_models()
            models_str = "\n".join(f"- {m}" for m in models_list)
            return f"[404] Model '{model}' not available. Choose one of the downloaded models:\n{models_str}"

        parsed_resp = resp.json()
        if "response" not in parsed_resp:
            return print(resp)
        reply = resp.json()["response"].strip()
        profile["history"].extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}])
        return reply
