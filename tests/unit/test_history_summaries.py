import pytest

import engine
from engine.backends.ollama import ensure_summary

# --- Helpers ---------------------------------------------------------------

ROLE_MAP = {"U": "user", "A": "assistant", "S": "system", "N": "system"}

def expand(tokens):
    """
    Expand a compact token list into a role-string.
    Tokens may be: 'U', 'A', 'S', 'N', 'UA*10', 'AU*3', etc.
    """
    out = []
    for t in tokens:
        if "*" in t:
            base, times = t.split("*")
            out.append(base * int(times))
        else:
            out.append(t)
    return "".join(out)

def to_history(seq):
    """Convert role-string to history list of dicts; 'S' is summary, 'N' is non-summary note."""
    out = []
    for ch in seq:
        role = ROLE_MAP[ch]
        msg = {"role": role, "content": ch}
        if ch == "S":
            msg["meta"] = {"kind": "summary"}
        elif ch == "N":
            msg["meta"] = {"kind": "note"}
        out.append(msg)
    return out

def roles(history):
    """Convert history list back to role-string for visual assertions."""
    out = []
    for msg in history:
        if msg["role"] == "system":
            out.append("S" if msg.get("meta", {}).get("kind") == "summary" else "N")
        else:
            out.append("U" if msg["role"] == "user" else "A")
    return "".join(out)

def catchup(history, chunk=10):
    """Run ensure_summary repeatedly (like query_ollama does)."""
    last = -1
    while True:
        idx = engine.backends.ollama.ensure_summary(history, model="dummy", chunk_size=chunk)
        if idx <= last:
            break
        last = idx

# ---- Stub summarizer (deterministic) -------------------------------------

@pytest.fixture(autouse=True)
def stub_summarizer(monkeypatch):
    def fake_summarize(segment, model):
        ua = sum(1 for x in segment if x["role"] in ("user", "assistant"))
        return f"SUMMARY({ua})"
    monkeypatch.setattr(engine.backends.ollama, "summarize_history_offline", fake_summarize)
    yield

# ---- 10 visual scenarios --------------------------------------------------

SCENARIOS = [
    # 1) <10 U/A → no summary
    (["UA*4", "U"],                        ["UA*4", "U"]),

    # 2) exactly 10 U/A → one summary appended after the 10th
    (["UA*5"],                             ["UA*5", "S"]),

    # 3) 15 U/A → one summary at 10, 5 tail remain
    (["UA*5", "UAUAA"],                    ["UA*5", "S", "UAUAA"]),

    # 4) 20 U/A → two summaries (after 10 and after 20)
    (["UA*10"],                            ["UA*5", "S", "UA*5", "S"]),

    # 5) 25 U/A → two summaries + 5 tail
    (["UA*12", "U"],                       ["UA*5", "S", "UA*5", "S", "UA*2", "U"]),

    # 6) 9 U/A, then a non-summary system note, then 1 U/A → summary after the 10th U/A
    (["UA*4", "U", "N", "U"],              ["UA*4", "U", "N", "U", "S"]),

    # 7) existing summary, then <10 U/A → no new summary
    (["UA*5", "S", "UA*4"],                ["UA*5", "S", "UA*4"]),

    # 8) existing summary, then exactly 10 U/A → another summary
    (["UA*5", "S", "UA*5"],                ["UA*5", "S", "UA*5", "S"]),

    # 9) many summaries already (>5), then 9 U/A → still no new summary
    (((["UA*5", "S"] * 5) + ["UA*4", "U"]), ((["UA*5", "S"] * 5) + ["UA*4", "U"])),

    # 10) 37 U/A (no existing summaries) → summaries after 10 and 20, 17 tail remain
    (["UA*18", "U"],                       ["UA*5", "S", "UA*5", "S", "UA*5", "S", "UA*3", "U"]),
]

@pytest.mark.parametrize("before_tokens, expected_tokens", SCENARIOS)
def test_ensure_summary_10_visual_cases(before_tokens, expected_tokens):
    before = expand(before_tokens)
    expected = expand(expected_tokens)
    h = to_history(before)
    catchup(h, chunk=10)
    assert roles(h) == expected

# -------------------- EXTENSION: prompt construction tests (visual, generic) --------------------

def prompt_visual_from_trimmed(trimmed_msgs):
    """
    Build a HUMAN-READABLE visual sequence of the prompt lines (excluding content),
    using the same role rules as your generic tests:
      - 'SYS'  : the top system prompt line (first line in msgs)
      - 'S'    : system summary (meta.kind == 'summary')
      - 'N'    : other system note (non-summary system message)
      - 'U'    : user
      - 'A'    : assistant
      - 'END'  : final 'Assistant:' line
    """
    visual = []
    for i, m_ in enumerate(trimmed_msgs):
        if m_["role"] == "system":
            if i == 0 and m_.get("meta", {}).get("kind") != "summary":
                visual.append("SYS")
            else:
                visual.append("S" if m_.get("meta", {}).get("kind") == "summary" else "N")
        elif m_["role"] == "user":
            visual.append("U")
        elif m_["role"] == "assistant":
            visual.append("A")
        else:
            visual.append("?")
    visual.append("END")  # for the trailing "Assistant:" line
    return " ".join(visual)

def build_prompt_from_trimmed(trimmed_msgs):
    """Recreate the exact prompt string the code sends to Ollama."""
    lines = []
    for m_ in trimmed_msgs:
        role = "Assistant (memory summary)" if m_["role"] == "system" else m_["role"].capitalize()
        lines.append(f"{role}: {m_['content']}")
    last_message = trimmed_msgs[len(trimmed_msgs) - 1]
    lines.append(f"User: {last_message['content']}")
    return "\n".join(lines) + "\nAssistant:"

@pytest.fixture
def stub_trim_and_requests(monkeypatch):
    """
    Capture the 'trimmed' messages (from trim_message_history) and the
    outgoing prompt text (requests.post json["prompt"]) without changing any production code.
    """
    captured = {"trimmed": None, "prompt": None}

    def identity_trim(msgs, model, current_prompt):
        captured["trimmed"] = msgs
        return msgs

    class DummyResp:
        def __init__(self):
            self.status_code = 200
        def json(self):
            return {"response": "OK"}
        def raise_for_status(self): return None

    def fake_post(url, json=None, stream=False):
        captured["prompt"] = json["prompt"]
        return DummyResp()

    monkeypatch.setattr(engine.backends.ollama, "trim_message_history", identity_trim)
    monkeypatch.setattr(engine.backends.ollama.requests, "post", fake_post)
    return captured

# --- Visual prompt scenarios (human-verifiable) ----------------------------
# Each case uses the SAME compact role notation you already adopted.
# We verify the *visual* prompt structure (roles only) AND the exact prompt text.

PROMPT_VISUAL_CASES = [
    # 1) No summaries, <10 U/A total → prompt = SYS + all history (incl. newly added user) + END
    (["UA*2"],                           "SYS U A U A U END"),

    # 2) Exactly 10 U/A after adding the new user → summary inserted before the new turn's assistant; prompt = SYS S + new user + END
    (["UA*5"],                           "SYS S U END"),

    # 3) Existing summary, then <10 U/A since it → prompt = SYS S + (those U/A) + new user + END
    (["UA*5", "S", "UA*3"],              "SYS S U A U A U A U END"),

    # 4) Existing summary, then exactly 10 U/A after adding the new user → new summary added; prompt = SYS S S + new user + END
    (["UA*5", "S", "UA*5"],              "SYS S S U END"),

    # 5) >5 summaries total → only last 5 kept; prompt = SYS S S S S S + tail after last summary (U/A) + new user + END
    (((["UA*5", "S"] * 6) + ["UA*2"]),   "SYS S S S S S U A U A U END"),

    # 6) Interleaved non-summary system note (N) does NOT count toward the 10 → summary lands after the 10th U/A (which is the new user here); prompt = SYS S END
    (["UA*4", "U", "N", "U"],            "SYS S U END"),

    # 7) Existing summary, then 9 U/A → still no new summary; prompt = SYS S + 9 U/A + new user + END
    (["UA*5", "S", "UA*4"],              "SYS S U A U A U A U A U END"),

    # 8) Many summaries (exactly 5), then 10th U/A with the new user → new summary; prompt keeps last 5 (incl. the new one); tail empty
    (((["UA*5", "S"] * 5) + ["UA*4"]), "SYS S S S S S U A U A U A U A U END"),
]

@pytest.mark.parametrize("before_tokens, expected_visual", PROMPT_VISUAL_CASES)
def test_prompt_visual_and_exact_text(before_tokens, expected_visual,
                                      stub_summarizer, stub_trim_and_requests):
    """
    Human-friendly test: we assert a compact VISUAL sequence of roles in the prompt,
    and also assert the exact text equals the join() used in production.
    """
    system_prompt = "SYS"
    user_prompt = "UP"
    profile = {"history": to_history(expand(before_tokens))}
    settings = {"llm_model": "dummy", "streaming": False}

    # Call the real function (without modifying code)
    engine.backends.ollama.query_ollama(
        prompt=user_prompt,
        system_prompt=system_prompt,
        profile=profile,
        settings=settings,
        force_stream=False,
    )

    trimmed = stub_trim_and_requests["trimmed"]
    sent_prompt = stub_trim_and_requests["prompt"]

    # 1) Visual check (humans can quickly verify roles and order)
    visual = prompt_visual_from_trimmed(trimmed)
    assert visual == expected_visual

    # 2) Exact prompt string equality (full fidelity check)
    expected_prompt = build_prompt_from_trimmed(trimmed)
    assert sent_prompt == expected_prompt
