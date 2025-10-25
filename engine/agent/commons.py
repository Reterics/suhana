from typing import Any, Generator, LiteralString, Iterable, Optional
import requests
import json
from datetime import datetime

def _extract_balanced_json(text: str, start: int) -> Optional[str]:
    """Return a balanced JSON substring starting at `start` (which must be '{' or '[').
    Handles nested braces and ignores braces inside quoted strings."""
    if start < 0 or start >= len(text) or text[start] not in "{[":
        return None
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    stack = [opener]
    i = start
    in_string = False
    escape = False

    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                # Only pop if it matches the expected closer for the current opener
                want = "}" if stack[-1] == "{" else "]"
                if ch == want:
                    stack.pop()
                    if not stack:
                        # i is the index of the matching closing char
                        return text[start:i + 1]
                else:
                    # mismatched brace—bail
                    return None
        i += 1
    return None  # Unbalanced

def _extract_slice_to_last_closer(text: str, start: int) -> Optional[str]:
    """Fallback: slice from first opener to the last matching closer char in the whole text."""
    if text[start] not in "{[":
        return None
    closer = "}" if text[start] == "{" else "]"
    end = text.rfind(closer)
    if end == -1 or end <= start:
        return None
    candidate = text[start:end + 1]
    try:
        json.loads(candidate)
        return candidate
    except Exception:
        return None

def extract_code_from_markdown(markdown: str, code_type: str) -> str | None:
    start = markdown.find("```")
    if start != -1:
        end = markdown.find("```", start + 3)
        if end != -1:
            block = markdown[start + 3 : end].strip()
            if block.lower().startswith(code_type):
                block = block[len(code_type):].strip()
            return block

    return None

def extract_json_from_raw_text(text:str) -> str | None:
    idx_obj = text.find("{")
    idx_arr = text.find("[")
    starts = [i for i in (idx_obj, idx_arr) if i != -1]
    if not starts:
        return None
    start = min(starts)
    clean_text = _extract_balanced_json(text, start)
    if clean_text is None:
        return _extract_slice_to_last_closer(text, start)
    return clean_text


def _ollama_generate(
    model: str, system_prompt: str, user_input: str, stream: bool = False
):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": user_input,
        "system": system_prompt,
        "stream": stream,
    }
    if not stream:
        resp = requests.post(url, json=payload)
        if resp.status_code == 404:
            return f"[404] Model '{model}' not available in Ollama. Please pull it (e.g., 'ollama pull {model}')."
        resp.raise_for_status()
        data = resp.json()
        return (data.get("response") or "").strip()
    else:
        def gen():
            with requests.post(url, json=payload, stream=True) as r:
                if r.status_code == 404:
                    yield f"[404] Model '{model}' not available in Ollama. Please pull it (e.g., 'ollama pull {model}')."
                    return
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        token = obj.get("response", "")
                        if token:
                            yield token
                    except Exception:
                        # Best-effort: ignore malformed lines
                        continue
        return gen()


def ask(
        model: str,
    system_prompt: str,
    user_input: str,
) -> str | None:
    # Always use direct Ollama path with no conversation history
    return str(_ollama_generate(model=model, system_prompt=system_prompt, user_input=user_input, stream=False))


def ask_stream(
        model: str,
    system_prompt: str,
    user_input: str,
) -> Iterable[str]:
    # Always use direct Ollama generator with no conversation history
    gen = _ollama_generate(model=model, system_prompt=system_prompt, user_input=user_input, stream=True)
    if isinstance(gen, str):
        yield gen
    else:
        for chunk in gen:
            if chunk:
                yield chunk

def now_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")
