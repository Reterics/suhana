import requests
import json
from datetime import datetime
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
        flat += f"{'User' if role == 'user' else 'Assistant'}: {msg['content']}\n"

    prompt = (f"Summarize the following chat as concise bullet points.\n"
              f"- Capture only facts, goals, and technical decisions.\n"
              f"- Do not narrate or write in first person.\n"
              f"- Output only bullet points.\n\n"
              f"Chat content: {flat}")
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

CHUNK_SIZE = 10
NUM_SUMMARIES = 5

def is_summary(m):
    return m.get("role") == "system" and m.get("meta", {}).get("kind") == "summary"

def ensure_summary(history, model, chunk_size=10):
    """
    If there are >= chunk_size user/assistant messages since the last summary,
    insert one new summary immediately after that chunk. Otherwise do nothing.
    Returns the index of the last summary after this function (or -1 if none).
    """
    # 1) find last summary index
    last_summary_idx = -1
    for i in range(len(history)-1, -1, -1):
        if is_summary(history[i]):
            last_summary_idx = i
            break

    # 2) count U/A messages since last summary, and find the exact end index of the chunk
    ua_count = 0
    chunk_end_idx = None
    start = last_summary_idx + 1
    for i in range(start, len(history)):
        if history[i]["role"] in ("user", "assistant"):
            ua_count += 1
            if ua_count == chunk_size:
                chunk_end_idx = i  # this is the index of the 10th U/A since last summary
                break

    # 3) if we don’t have a full chunk yet, nothing to do
    if chunk_end_idx is None:
        return last_summary_idx

    # 4) build the summary over exactly those U/A messages (and any system notes in between if you want)
    old_segment = history[start:chunk_end_idx+1]  # inclusive
    summary_text = summarize_history_offline(old_segment, model)
    summary_msg = {
        "role": "system",
        "content": summary_text,  # or prefixed with "Summary of earlier conversation: ..."
        "created_at": datetime.now().isoformat(),
        "meta": {"kind": "summary", "model": model}
    }

    # 5) insert the summary **right after** the 10th message of the chunk
    insert_at = chunk_end_idx + 1
    history.insert(insert_at, summary_msg)
    return insert_at

def build_context(history, num_summaries=NUM_SUMMARIES):
    # find all summaries
    summary_indices = [i for i, m in enumerate(history)
                       if isinstance(m, dict) and m.get("role") == "system" and (m.get("meta", {}).get("kind") == "summary")]

    if not summary_indices:
        return history

    chosen_sum_idxs = summary_indices[-num_summaries:]

    last_sum_idx = summary_indices[-1]
    recent_chunk = history[last_sum_idx+1:]

    chosen = [history[i] for i in chosen_sum_idxs] + recent_chunk
    return chosen

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

    # Add user message to history immediately
    profile.setdefault("history", [])
    profile["history"].append({"role": "user", "content": prompt, "created_at": datetime.now().isoformat()})

    # catch-up mode: insert all summaries needed right now
    last_idx = -1
    while True:
        inserted_at = ensure_summary(profile["history"], model, chunk_size=10)
        if inserted_at <= last_idx:  # no new summary inserted
            break
        last_idx = inserted_at

    msgs = [{"role": "system", "content": system_prompt}] + build_context(profile["history"], num_summaries=NUM_SUMMARIES)

    trimmed = trim_message_history(msgs, model="gpt-3.5-turbo", current_prompt=prompt)
    text = "\n".join([f"{m['role'].capitalize() if m['role'] != 'system' else 'Assistant (memory summary)'}: {m['content']}" for m in trimmed])
    text += f"\nUser: {prompt}\nAssistant:"

    # open('prompt_log.txt', 'w').write(text)
    if stream:
        def stream_generator():
            stream_reply = ""
            with requests.post("http://localhost:11434/api/generate",
                               json={"model": model, "prompt": text, "stream": True, "options": {
                                    "temperature": 0.2,
                                    "repeat_penalty": 1.2,
                                    "stop": ["User:", "System:"]}}, stream=True) as resp:
                resp.raise_for_status()  # Raises an exception for 4xx/5xx errors
                for line in resp.iter_lines():
                    if line:
                        data = json.loads(line)
                        token = data.get("response", "")
                        stream_reply += token
                        yield token
            # Only add assistant's reply since user's message was already added
            profile["history"].append({"role": "assistant", "content": stream_reply, "created_at": datetime.now().isoformat()})

        # Wrap the generator with error handling
        return handle_streaming_errors("Ollama", stream_generator)()
    else:
        resp = requests.post("http://localhost:11434/api/generate", json={"model": model, "prompt": text, "stream": False})
        if resp.status_code == 404:
            models_list = get_downloaded_models()
            if not models_list:
                return "[404] No models are available. Please download a model using Ollama CLI (e.g., 'ollama pull mistral') or configure a different AI API."
            models_str = "\n".join(f"- {m}" for m in models_list)
            return f"[404] Model '{model}' not available. Choose one of the downloaded models:\n{models_str}"

        parsed_resp = resp.json()
        if "response" not in parsed_resp:
            return print(resp)
        reply = resp.json()["response"].strip()
        # Only add assistant's reply since user's message was already added
        profile["history"].append({"role": "assistant", "content": reply, "created_at": datetime.now().isoformat()})
        return reply
