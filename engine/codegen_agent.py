#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Suhana CodeGen Agent – FastAPI endpoint (Python 3.12+)

Planner → Coder → Critic controller wrapped behind HTTP.

Notes
-----
- Requires `git` on PATH.
- Controller does not install deps; it only runs your configured commands.
- Save this file with UTF-8 encoding and LF newlines.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Optional

import requests

from fastapi import HTTPException
from pydantic import BaseModel, Field

from engine.utils import configure_logging

logger = configure_logging(__name__)

# ---------------------------------------------------------------------------
# Prompts (concise system prompts; see earlier detailed versions)
# ---------------------------------------------------------------------------
PLANNER_SYSTEM = """
You are the PLANNER in a 3-stage code-gen agent.
Goal: emit a single, valid JSON plan for a small, safe change in a TS/React + Laravel/PHP monorepo.

INPUT
A JSON object:
{
  "format": "planner_input_v1",
  "sections": {
    "task": "...",
    "repo_map": [...],
    "relevant_excerpts": "...",
    "constraints": [...]
  }
}

OUTPUT (STRICT JSON ONLY; no markdown, no comments)
{
  "rationale": "≤500 chars explaining the approach.",
  "acceptance_checks": ["≤6 short, testable bullets"],
  "impacted": [
    {
      "path": "relative/path.ext",
      "reason": "≤200 chars",
      "operations": ["edit"|"add"|"remove"],
      "symbols": ["Class#method"|"functionName"|"ComponentName"],
      "risk": "low"|"medium"|"high"
    }
  ],
  "tests": {
    "strategy": "unit"|"integration"|"both",
    "existing_suites": ["paths..."],
    "new_tests": [
      {"path": "path/to/new/test", "why": "≤120 chars"}
    ]
  },
  "migrations": {"need": false, "files": [], "notes": ""},
  "firebase_rules": {"touch": false, "paths": [], "checks": []},
  "commands": [
    {"name": "php_tests", "cmd": "php artisan test --testsuite=Feature", "when": "after_patch"}
  ],
  "constraints": ["repeat or summarize key constraints from input"]
}

RULES
1) Output ONLY one JSON object; valid syntax; double quotes; no trailing commas.
2) Prefer the smallest viable change; reuse existing code where possible.
3) Stay within the task; do not invent unrelated files/paths/features.
4) If info is missing, infer sensible defaults; keep changes minimal.
5) Keep lists compact: acceptance_checks ≤6, impacted ≤8, symbols ≤6.
6) Default values if uncertain:
   - tests.strategy: "unit"
   - migrations.need: false
   - firebase_rules.touch: false
7) If the task is unsafe, out of scope, or cannot be planned, return a safe no-op:
   {
     "rationale": "Blocked: reason (≤200 chars).",
     "acceptance_checks": [],
     "impacted": [],
     "tests": {"strategy":"unit","existing_suites":[],"new_tests":[]},
     "migrations":{"need":false,"files":[],"notes":""},
     "firebase_rules":{"touch":false,"paths":[],"checks":[]},
     "commands": [],
     "constraints": []
   }
8) Respect any explicit constraints from input (e.g., patch-only, path allowlist).
Answer with only JSON format.
"""


CODER_SYSTEM = """
You are the CODER.
Given a plan and code excerpts, output ONLY one valid unified diff patch.

Rules:
1) Must apply with: git apply --index -p0
2) Edit ONLY files in plan.impacted[].path
3) Edit ONLY inside the provided excerpts; if a needed symbol or line is NOT present in excerpts, emit nothing.
4) Keep edits minimal; do not add deps, files, or features not in plan.
5) Every hunk must match existing lines exactly (preimage lines must exist).
6) If anything is unclear or risky → emit nothing.

Example:
diff --git a/package.json b/package.json
index 1111111..2222222 100644
--- a/package.json
+++ b/package.json
@@ -3,7 +3,7 @@
   "name": "my-project",
-  "react": "^16.8.4"
+  "react": "^17.0.1"
 }

Answer with only the diff.
"""

CRITIC_SYSTEM = (
    "You are the CRITIC. Given the plan and failing outputs, return a SMALL unified diff fixing the root cause. No prose."
)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
class ModelConfig(BaseModel):
    planner: str
    coder: str
    critic: str

class RunRequest(BaseModel):
    repo: str
    ticket: str
    allow: List[str] = Field(default_factory=lambda: [
        "apps/**/src", "packages/**/src", "backend/**", "tests/**", "database/migrations/**"
    ])
    backend_name: str
    models: ModelConfig
    constraints: List[str] = Field(default_factory=list)
    timeout_sec: int = 900
    max_map: int = 1500
    profile: Dict[str, Any] = Field(default_factory=dict)
    settings: Dict[str, Any] = Field(default_factory=dict)

class CommandOutcome(BaseModel):
    name: str
    ok: bool
    code: int

class RunResponse(BaseModel):
    status: str
    artifacts_dir: str
    plan: Dict[str, Any]
    touched_files: List[str]
    logs: Dict[str, Any]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

@dataclass
class CmdResult:
    ok: bool
    code: int
    out: str
    err: str

def run_cmd(cmd: str, cwd: Path, timeout: int) -> CmdResult:
    # Use shell=True to allow full command strings (pnpm/php artisan/etc.).
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=os.environ.copy(),
    )
    return CmdResult(ok=(proc.returncode == 0), code=proc.returncode, out=proc.stdout, err=proc.stderr)

LANG_BY_EXT = {
    ".ts": "ts", ".tsx": "tsx", ".php": "php", ".js": "js", ".jsx": "jsx", ".py": "py", ".json": "json"
}
EXCLUDED_DIRS = {
    "venv", ".venv", "env", ".env",
    "node_modules", "bower_components",
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache",
    "dist", "build", "out", ".next", ".turbo",
    ".idea", ".vscode", ".DS_Store"
}

def build_repo_map(root: Path, max_files: int, include_globs: List[str]) -> List[Dict[str, Any]]:
    """
    Scan repository files, collecting a small summary for each.
    Excludes typical virtualenv, cache, and build directories.
    """
    items: List[Dict[str, Any]] = []

    for p in sorted(root.rglob("*")):
        # Skip excluded directories early
        parts = set(p.parts)
        if parts & EXCLUDED_DIRS:
            continue

        if not p.is_file():
            continue

        rel = p.relative_to(root).as_posix()

        # Filter by include patterns (allowlist)
        if not any(fnmatch(rel, g) for g in include_globs):
            continue

        # Filter by supported file extensions
        if p.suffix.lower() not in LANG_BY_EXT:
            continue

        try:
            with p.open("r", encoding="utf-8", errors="ignore") as f:
                loc = sum(1 for _ in f)
        except Exception:
            loc = 0

        items.append({
            "path": rel,
            "lang": LANG_BY_EXT[p.suffix.lower()],
            "loc": loc
        })

        if len(items) >= max_files:
            break

    return items


# Diff validation & apply
DIFF_HEADER_RE = re.compile(r"^--- (?:a/)?(.+)$")
PLUS_HEADER_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")

def validate_unified_diff(diff_text: str, allow_globs: List[str]) -> Tuple[bool, str, List[str]]:
    # normalize and jump to first actual diff
    lines = [ln.rstrip("\n\r") for ln in diff_text.splitlines()]
    for k, ln in enumerate(lines):
        if ln.lstrip().startswith("diff --git"):
            lines = lines[k+1:]  # headers come after this line
            break

    touched: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].lstrip()  # tolerate leading spaces
        if line.startswith("--- "):
            m1 = DIFF_HEADER_RE.match(line)  # match on stripped line
            next_line = lines[i + 1].lstrip() if i + 1 < len(lines) else ""
            m2 = PLUS_HEADER_RE.match(next_line)
            if not (m1 and m2):
                return False, f"Malformed diff headers near line {i + 1}", []
            old_path = m1.group(1)
            new_path = m2.group(1)
            path = new_path if new_path != "/dev/null" else old_path
            path = path.replace("\\", "/")
            if path.startswith(("a/", "b/")):
                path = path[2:]

            forbidden = (".env" in path) or path.endswith(("package-lock.json", "yarn.lock", "pnpm-lock.yaml"))
            if forbidden:
                return False, f"Forbidden target in diff: {path}", []

            if not any(fnmatch(path, g) for g in allow_globs):
                return False, f"Path not allowed by allowlist: {path}", []

            touched.append(path)
            i += 1  # we've already looked at the +++ line via next_line
        i += 1

    if not touched:
        return False, "No file headers found in diff.", []
    return True, "OK", sorted(set(touched))


def git_apply(diff_text: str, repo_root: Path) -> Tuple[bool, str]:
    patch_file = repo_root / f".agent_patch_{now_stamp()}.diff"
    logger.info(f"Write git diff into {patch_file}")
    patch_file.write_text(diff_text, encoding="utf-8")

    cmd = ["git", "-C", str(repo_root), "apply", "--whitespace=fix", str(patch_file)]
    logger.info(f"Execute: {' '.join(cmd)}")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return True, "applied"
    return False, (proc.stderr or proc.stdout)

# Snippets

def read_excerpt(path: Path, start: int, end: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        start = max(1, start)
        end = min(len(lines), end)
        chunk = lines[start - 1 : end]
        return f"FILE: {path.as_posix()}\nLINES: {start}-{end}\n" + "\n".join(chunk)
    except Exception as e:  # pragma: no cover
        return f"FILE: {path.as_posix()}\nERROR: {e}"


def collect_snippets(repo_root: Path, impacted: List[Dict[str, Any]], context_lines: int = 160) -> str:
    blocks: List[str] = []
    for item in impacted:
        rel = item.get("path")
        if not rel:
            continue
        p = repo_root / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        symbols: List[str] = (item.get("symbols") or [])
        if not symbols:
            blocks.append(read_excerpt(p, 1, min(len(lines), context_lines)))
            continue
        for sym in symbols[:4]:
            needle = re.escape(sym.split("#")[-1].rstrip("()"))
            matches = list(re.finditer(needle, text))
            if not matches:
                continue
            for m in matches[:2]:
                line_no = text[: m.start()].count("\n") + 1
                start = max(1, line_no - context_lines // 2)
                end = min(len(lines), line_no + context_lines // 2)
                blocks.append(read_excerpt(p, start, end))
    return "\n\n=====\n\n".join(blocks)


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

# ---------------------------------------------------------------------------
# LLM Broker (Ollama-only, no history)
# ---------------------------------------------------------------------------
class LLMBroker:
    """Minimal broker for the CodeGen Agent.

    Only supports the 'ollama_backend' and calls Ollama directly without any
    chat history, sending only system prompt + user input.
    """
    def __init__(self):
        self.backend_name = "ollama_backend"

    # --- Direct Ollama calls (no history) ---
    def _ollama_generate(self, model: str, system_prompt: str, user_input: str, stream: bool = False):
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
        self,
        model: str,
        system_prompt: str,
        user_input: str,
        profile: Dict[str, Any],
        settings: Dict[str, Any],
    ) -> str:
        # Always use direct Ollama path with no conversation history
        return self._ollama_generate(model=model, system_prompt=system_prompt, user_input=user_input, stream=False)

    def ask_stream(
        self,
        model: str,
        system_prompt: str,
        user_input: str,
        profile: Dict[str, Any],
        settings: Dict[str, Any],
    ) -> Iterable[str]:
        # Always use direct Ollama generator with no conversation history
        gen = self._ollama_generate(model=model, system_prompt=system_prompt, user_input=user_input, stream=True)
        if isinstance(gen, str):
            yield gen
        else:
            for chunk in gen:
                if chunk:
                    yield chunk

# ---------------------------------------------------------------------------
# Core run logic (non-streaming)
# ---------------------------------------------------------------------------
REPAIR_MAX = 3

def run_once(req: RunRequest) -> RunResponse:
    repo = Path(req.repo).resolve()
    if not repo.exists():
        raise HTTPException(400, f"Repo not found: {repo}")

    artifacts_root = (repo / ".agent_artifacts" / now_stamp()).resolve()
    artifacts_root.mkdir(parents=True, exist_ok=True)

    # 1) Repo map
    repo_map = build_repo_map(repo, max_files=req.max_map, include_globs=req.allow)

    # 2) Planner
    planner_user = json.dumps({
        "format": "planner_input_v1",
        "sections": {
            "task": (req.ticket or "").strip(),
            "repo_map": repo_map,  # already a JSON-serializable list
            "relevant_excerpts": "(none yet — controller collects after plan)",
            "constraints": req.constraints or [
                "patch-only unified diff",
                "respect path allowlist"
            ]
        }
    }, ensure_ascii=False)

    broker = LLMBroker()
    plan_text = broker.ask(req.models.planner, PLANNER_SYSTEM, planner_user, req.profile, req.settings)
    (artifacts_root / "plan_raw.txt").write_text(plan_text, encoding="utf-8")
    try:
        plan = json.loads(plan_text)
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"Planner returned invalid JSON: {e}")
    (artifacts_root / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 3) Snippets
    snippets = collect_snippets(repo, plan.get("impacted", []), context_lines=160)

    # 4) Coder
    coder_user = (
        "[PLAN_JSON]\n"
        + json.dumps(plan, ensure_ascii=False)
        + "\n\n"
        + "[RELEVANT_EXCERPTS]\n"
        + snippets
        + "\n"
    )
    coder_diff = broker.ask(
        req.models.coder, CODER_SYSTEM, coder_user, req.profile, req.settings
    )

    clean_diff = coder_diff.strip()

    # If it doesn't start with a valid diff, try to extract fenced block
    if not clean_diff.startswith("diff --git"):
        logger.info(f"Not a diff format, Fallback to markdown.")
        start = clean_diff.find("```")
        if start != -1:
            end = clean_diff.find("```", start + 3)
            if end != -1:
                block = clean_diff[start + 3:end].strip()
                if block.lower().startswith("diff"):
                    block = block[4:].strip()
                clean_diff = block
                logger.info("Diff extracted from markdown.")
            logger.warning("Markdown diff end detection failed.")
        else:
            logger.warning("Markdown diff detection failed.")

    (artifacts_root / "coder.diff").write_text(clean_diff, encoding="utf-8")

    ok, msg, touched = validate_unified_diff(clean_diff, req.allow)
    if not ok:
        raise HTTPException(400, f"Coder diff invalid: {msg}")

    ok_apply, apply_msg = git_apply(clean_diff, repo)
    if not ok_apply:
        (artifacts_root / "apply_error.txt").write_text(apply_msg, encoding="utf-8")
        raise HTTPException(500, f"git apply failed: {apply_msg}")

    # 5) Commands (after_patch)
    cmd_results: List[Tuple[str, CmdResult]] = []
    for c in plan.get("commands", []):
        if c.get("when") == "after_patch":
            name = c.get("name") or "cmd"
            res = run_cmd(c.get("cmd"), cwd=repo, timeout=req.timeout_sec)
            (artifacts_root / "logs").mkdir(exist_ok=True)
            (artifacts_root / "logs" / f"{name}.out.txt").write_text(res.out, encoding="utf-8")
            (artifacts_root / "logs" / f"{name}.err.txt").write_text(res.err, encoding="utf-8")
            cmd_results.append((name, res))

    def _all_ok() -> bool:
        return all(r.ok for _, r in cmd_results) if cmd_results else True

    # 6) Critic loop
    for i in range(REPAIR_MAX):
        if _all_ok():
            break
        combined: List[str] = []
        for name, r in cmd_results:
            if not r.ok:
                combined.append(
                    f"## {name} (exit={r.code})\nSTDOUT:\n{r.out[-50000:]}\n\nSTDERR:\n{r.err[-50000:]}\n"
                )
        test_output = "\n\n".join(combined)[:200_000]

        critic_user = (
            "[PLAN_JSON]\n" + json.dumps(plan, ensure_ascii=False) + "\n\n" +
            "[TEST_OUTPUT]\n" + test_output + "\n\n" +
            "[RELEVANT_EXCERPTS]\n" + snippets + "\n"
        )
        critic_diff = broker.ask(req.models.critic, CRITIC_SYSTEM, critic_user, req.profile, req.settings)
        (artifacts_root / "critic").mkdir(exist_ok=True)
        (artifacts_root / "critic" / f"critic_{i + 1}.diff").write_text(critic_diff, encoding="utf-8")

        ok, msg, _ = validate_unified_diff(critic_diff, req.allow)
        if not ok:
            raise HTTPException(400, f"Critic diff invalid: {msg}")
        ok_apply, apply_msg = git_apply(critic_diff, repo)
        if not ok_apply:
            (artifacts_root / "critic" / f"critic_apply_error_{i + 1}.txt").write_text(apply_msg, encoding="utf-8")
            raise HTTPException(500, f"git apply (critic) failed: {apply_msg}")

        # re-run commands
        cmd_results = []
        for c in plan.get("commands", []):
            if c.get("when") == "after_patch":
                name = c.get("name") or "cmd"
                res = run_cmd(c.get("cmd"), cwd=repo, timeout=req.timeout_sec)
                (artifacts_root / "logs" / f"{name}.out.txt").write_text(res.out, encoding="utf-8")
                (artifacts_root / "logs" / f"{name}.err.txt").write_text(res.err, encoding="utf-8")
                cmd_results.append((name, res))

    if not _all_ok():
        raise HTTPException(500, "Some commands still failing after Critic loop. See artifacts.")

    log_paths = {
        "plan": str((artifacts_root / "plan.json").resolve()),
        "coder_diff": str((artifacts_root / "coder.diff").resolve()),
        "logs_dir": str((artifacts_root / "logs").resolve()),
    }

    return RunResponse(
        status="ok",
        artifacts_dir=str(artifacts_root),
        plan=plan,
        touched_files=touched,
        logs={
            "commands": [CommandOutcome(name=n, ok=r.ok, code=r.code).model_dump() for n, r in cmd_results],
            "paths": log_paths,
        },
    )

# ---------------------------------------------------------------------------
# Streaming (NDJSON) runner
# ---------------------------------------------------------------------------

def ndjson(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"

EVENT_BUFFER_LIMIT = 200_000

def run_stream(req: RunRequest) -> Iterable[str]:
    repo = Path(req.repo).resolve()
    if not repo.exists():
        yield ndjson({"event": "error", "data": f"Repo not found: {repo}"})
        return

    artifacts_root = (repo / ".agent_artifacts" / now_stamp()).resolve()
    (artifacts_root / "logs").mkdir(parents=True, exist_ok=True)
    (artifacts_root / "critic").mkdir(parents=True, exist_ok=True)

    broker = LLMBroker()
    # Repo map
    repo_map = build_repo_map(repo, max_files=req.max_map, include_globs=req.allow)
    yield ndjson({"event": "repo_map", "data": {"count": len(repo_map)}})

    # Planner
    planner_user = json.dumps(
        {
            "format": "planner_input_v1",
            "sections": {
                "task": (req.ticket or "").strip(),
                "repo_map": repo_map,  # already a JSON-serializable list
                "relevant_excerpts": "(none yet — controller collects after plan)",
                "constraints": req.constraints
                or ["patch-only unified diff", "respect path allowlist"],
            },
        },
        ensure_ascii=False,
    )
    # "system": PLANNER_SYSTEM, "prompt": planner_user
    yield ndjson({"event": "planner_start", "data": {"model": req.models.planner}})
    plan_chunks: List[str] = []
    for chunk in broker.ask_stream(
        req.models.planner, PLANNER_SYSTEM, planner_user, req.profile, req.settings
    ):
        plan_chunks.append(chunk)
        yield ndjson({"event": "planner_chunk", "data": chunk[-EVENT_BUFFER_LIMIT:]})
    plan_text = "".join(plan_chunks)
    (artifacts_root / "plan_raw.txt").write_text(plan_text, encoding="utf-8")

    plan = None
    try:
        plan = json.loads(plan_text)
        yield ndjson({"event": "planner_done", "data": {"ok": True}})
    except json.JSONDecodeError:
        yield ndjson(
            {"event": "planner_fallback", "data": f"Invalid JSON, fallback to Markdown"}
        )

    clean_text = None

    if plan is None:
        start = plan_text.find("```")
        if start != -1:
            end = plan_text.find("```", start + 3)
            if end != -1:
                block = plan_text[start + 3:end].strip()
                if block.lower().startswith("json"):
                    block = block[4:].strip()
                clean_text = block
        else:
            yield ndjson(
                {"event": "planner_fallback", "data": f"Invalid Markdown, fallback to raw JSON detection"}
            )
            idx_obj = plan_text.find("{")
            idx_arr = plan_text.find("[")
            starts = [i for i in (idx_obj, idx_arr) if i != -1]
            if not starts:
                return None
            start = min(starts)
            clean_text = _extract_balanced_json(plan_text, start)
            if clean_text is None:
                clean_text = _extract_slice_to_last_closer(plan_text, start)

    if clean_text is None and plan is None:
        yield ndjson({"event": "error", "data": f"Planner has no JSON content"})
        return
    elif plan is None:
        try:
            plan = json.loads(clean_text)
            yield ndjson({"event": "planner_done", "data": {"ok": True}})
        except json.JSONDecodeError as e:  # stop
            yield ndjson({"event": "error", "data": f"Planner invalid JSON: {e}"})
            return
    (artifacts_root / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    # Snippets
    snippets = collect_snippets(repo, plan.get("impacted", []), context_lines=160)
    yield ndjson({"event": "snippets_ready", "data": {"len": len(snippets)}})

    # Coder
    coder_user = (
        "[PLAN_JSON]\n"
        + json.dumps(plan, ensure_ascii=False)
        + "\n\n"
        + "[RELEVANT_EXCERPTS]\n"
        + snippets
        + "\n"
    )
    yield ndjson({"event": "coder_start", "data": {"model": req.models.coder}})
    diff_chunks: List[str] = []
    for chunk in broker.ask_stream(
        req.models.coder, CODER_SYSTEM, coder_user, req.profile, req.settings
    ):
        diff_chunks.append(chunk)
        yield ndjson({"event": "coder_chunk", "data": chunk[-EVENT_BUFFER_LIMIT:]})
    coder_diff = "".join(diff_chunks)

    clean_diff = coder_diff.strip()

    # If it doesn't start with a valid diff, try to extract fenced block
    if not clean_diff.startswith("diff --git"):
        logger.info(f"Not a diff format, Fallback to markdown.")
        start = clean_diff.find("```")
        if start != -1:
            end = clean_diff.find("```", start + 3)
            if end != -1:
                block = clean_diff[start + 3:end].strip()
                if block.lower().startswith("diff"):
                    block = block[4:].strip()
                clean_diff = block
                logger.info("Diff extracted from markdown.")
            logger.warning("Markdown diff end detection failed.")
        else:
            logger.warning("Markdown diff detection failed.")

    (artifacts_root / "coder.diff").write_text(clean_diff, encoding="utf-8")

    ok, msg, touched = validate_unified_diff(clean_diff, req.allow)
    if not ok:
        yield ndjson({"event": "error", "data": f"Coder diff invalid: {msg}"})
        return
    yield ndjson({"event": "diff_valid", "data": {"touched": touched}})

    ok_apply, apply_msg = git_apply(clean_diff, repo)
    if not ok_apply:
        (artifacts_root / "apply_error.txt").write_text(apply_msg, encoding="utf-8")
        yield ndjson({"event": "error", "data": f"git apply failed: {apply_msg}"})
        return
    yield ndjson({"event": "patch_applied", "data": "ok"})

    # Commands
    cmd_results: List[Tuple[str, CmdResult]] = []
    for c in plan.get("commands", []):
        if c.get("when") == "after_patch":
            name = c.get("name") or "cmd"
            yield ndjson({"event": "cmd_start", "data": {"name": name, "cmd": c.get("cmd")}})
            res = run_cmd(c.get("cmd"), cwd=repo, timeout=req.timeout_sec)
            (artifacts_root / "logs" / f"{name}.out.txt").write_text(res.out, encoding="utf-8")
            (artifacts_root / "logs" / f"{name}.err.txt").write_text(res.err, encoding="utf-8")
            cmd_results.append((name, res))
            yield ndjson({"event": "cmd_end", "data": {"name": name, "ok": res.ok, "code": res.code, "stdout": res.out[-EVENT_BUFFER_LIMIT:], "stderr": res.err[-EVENT_BUFFER_LIMIT:]}})

    def _all_ok() -> bool:
        return all(r.ok for _, r in cmd_results) if cmd_results else True

    # Critic loop
    for i in range(REPAIR_MAX):
        if _all_ok():
            break
        yield ndjson({"event": "critic_start", "data": {"iter": i + 1, "model": req.models.critic}})
        combined: List[str] = []
        for name, r in cmd_results:
            if not r.ok:
                combined.append(
                    f"## {name} (exit={r.code})\nSTDOUT:\n{r.out[-50000:]}\n\nSTDERR:\n{r.err[-50000:]}\n"
                )
        test_output = "\n\n".join(combined)[:200_000]

        critic_user = (
            "[PLAN_JSON]\n" + json.dumps(plan, ensure_ascii=False) + "\n\n" +
            "[TEST_OUTPUT]\n" + test_output + "\n\n" +
            "[RELEVANT_EXCERPTS]\n" + snippets + "\n"
        )
        critic_chunks: List[str] = []
        for chunk in broker.ask_stream(req.models.critic, CRITIC_SYSTEM, critic_user, req.profile, req.settings):
            critic_chunks.append(chunk)
            yield ndjson({"event": "critic_chunk", "data": chunk[-EVENT_BUFFER_LIMIT:]})
        critic_diff = "".join(critic_chunks)
        (artifacts_root / "critic" / f"critic_{i + 1}.diff").write_text(critic_diff, encoding="utf-8")

        ok, msg, _ = validate_unified_diff(critic_diff, req.allow)
        if not ok:
            yield ndjson({"event": "error", "data": f"Critic diff invalid: {msg}"})
            return
        ok_apply, apply_msg = git_apply(critic_diff, repo)
        if not ok_apply:
            (artifacts_root / "critic" / f"critic_apply_error_{i + 1}.txt").write_text(apply_msg, encoding="utf-8")
            yield ndjson({"event": "error", "data": f"git apply (critic) failed: {apply_msg}"})
            return
        yield ndjson({"event": "critic_patch_applied", "data": {"iter": i + 1}})

        # re-run commands
        cmd_results = []
        for c in plan.get("commands", []):
            if c.get("when") == "after_patch":
                name = c.get("name") or "cmd"
                yield ndjson({"event": "cmd_start", "data": {"name": name, "cmd": c.get("cmd")}})
                res = run_cmd(c.get("cmd"), cwd=repo, timeout=req.timeout_sec)
                (artifacts_root / "logs" / f"{name}.out.txt").write_text(res.out, encoding="utf-8")
                (artifacts_root / "logs" / f"{name}.err.txt").write_text(res.err, encoding="utf-8")
                cmd_results.append((name, res))
                yield ndjson({"event": "cmd_end", "data": {"name": name, "ok": res.ok, "code": res.code, "stdout": res.out[-EVENT_BUFFER_LIMIT:], "stderr": res.err[-EVENT_BUFFER_LIMIT:]}})

    if not _all_ok():
        yield ndjson({"event": "done", "data": {"ok": False, "message": "Some commands still failing after Critic loop."}})
        return

    yield ndjson({"event": "done", "data": {"ok": True, "artifacts_dir": str(artifacts_root)}})

