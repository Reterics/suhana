from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Dict, Any, Tuple, Optional, overload, Literal
import json
from pathlib import Path

from engine.coding_agent.models import RunRequest, RunResponse, CommandOutcome
from engine.coding_agent.coder import (
    CODER_SYSTEM,
    validate_unified_diff,
    git_apply,
    DIFF_DEBUGGER_SYSTEM,
    CmdResult,
    run_cmd,
)
from engine.coding_agent.commons import (
    ask,
    ask_stream,
    extract_json_from_raw_text,
    extract_code_from_markdown,
    now_stamp,
)
from engine.coding_agent.context import collect_snippets, build_repo_map
from engine.coding_agent.planner import PLANNER_SYSTEM, get_planner_input
from engine.utils import configure_logging

logger = configure_logging(__name__)

CRITIC_SYSTEM = (
    "You are the CRITIC. Given the plan and failing outputs, return a SMALL unified diff fixing the root cause. No prose."
)


@dataclass
class RunResult:
    ok: bool
    artifacts_dir: Optional[str] = None
    last_error: Optional[str] = None
    # if you want the raw NDJSON lines back:
    events: Optional[List[str]] = None

# ---------------------------------------------------------------------------
# Streaming (NDJSON) runner
# ---------------------------------------------------------------------------

def ndjson(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"

EVENT_BUFFER_LIMIT = 200_000

def _run_stream_iter(req) -> Iterable[str]:
    repo = Path(req.repo).resolve()
    if not repo.exists():
        yield ndjson({"event": "error", "data": f"Repo not found: {repo}"})
        return

    artifacts_root = (repo / ".agent_artifacts" / now_stamp()).resolve()
    (artifacts_root / "logs").mkdir(parents=True, exist_ok=True)
    (artifacts_root / "critic").mkdir(parents=True, exist_ok=True)

    # Planner
    plan = None
    max_planner_attempts = 3
    planner_user = get_planner_input(req)

    for attempt in range(max_planner_attempts):
        plan_chunks: List[str] = []
        for chunk in ask_stream(req.models.planner, PLANNER_SYSTEM, planner_user):
            plan_chunks.append(chunk)
            yield ndjson(
                {"event": "planner_chunk", "data": chunk[-EVENT_BUFFER_LIMIT:]}
            )

        plan_text = "".join(plan_chunks)
        (artifacts_root / "plan_raw.txt").write_text(plan_text, encoding="utf-8")

        try:
            plan = json.loads(plan_text)
            yield ndjson({"event": "planner_done", "data": {"ok": True}})
            break
        except json.JSONDecodeError:
            yield ndjson(
                {
                    "event": "planner_fallback",
                    "data": f"Invalid JSON (attempt {attempt + 1}) fallback to MD",
                }
            )

        clean_text = extract_code_from_markdown(
            plan_text, "json"
        ) or extract_json_from_raw_text(plan_text)

        if clean_text:
            try:
                plan = json.loads(clean_text)
                yield ndjson(
                    {
                        "event": "planner_done",
                        "data": {"ok": True, "attempt": attempt + 1, "fallback": True},
                    }
                )
                break
            except json.JSONDecodeError:  # stop
                yield ndjson(
                    {
                        "event": "planner_fallback",
                        "data": f"Fallback JSON invalid (attempt {attempt + 1})",
                    }
                )
                return
        else:
            yield ndjson(
                {
                    "event": "planner_fallback",
                    "data": f"No extractable JSON (attempt {attempt + 1})",
                }
            )

    if plan is None:
        yield ndjson({"event": "error", "data": f"Planner failed after {max_planner_attempts} attempts"})
        return
    (artifacts_root / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    success = False
    max_coder_attempts = 3
    last_err = None
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
        + "Answer with only the applicable git diff.\bGit Diff:\n"
    )
    yield ndjson({"event": "coder_start", "data": {"model": req.models.coder}})
    for attempt in range(max_coder_attempts):
        diff_chunks: List[str] = []
        for chunk in ask_stream(req.models.coder, CODER_SYSTEM, coder_user):
            diff_chunks.append(chunk)
            yield ndjson({"event": "coder_chunk", "data": chunk[-EVENT_BUFFER_LIMIT:]})
        coder_diff = "".join(diff_chunks).strip()

        # If it doesn't start with a valid diff, try to extract fenced block
        if not coder_diff.startswith("diff --git"):
            logger.info("Not a diff format, Fallback to markdown.")
            # TODO: make this an array
            clean_diff = extract_code_from_markdown(coder_diff, "diff") or ""
        else:
            clean_diff = coder_diff

        if not clean_diff:
            last_err = f"No diff content on attempt {attempt + 1}"
            yield ndjson({"event": "coder_fallback", "data": last_err})
            continue

        (artifacts_root / "coder.diff").write_text(clean_diff, encoding="utf-8")

        ok, msg, touched = validate_unified_diff(clean_diff, req.allow)
        if not ok:
            last_err = f"Coder diff invalid on attempt {attempt + 1}: {msg}"
            yield ndjson({"event": "coder_fallback", "data": last_err})
            continue

        yield ndjson(
            {
                "event": "diff_valid",
                "data": {"touched": touched, "attempt": attempt + 1},
            }
        )

        ok_apply, apply_msg, patch_file = git_apply(clean_diff, repo)
        if not ok_apply:
            (artifacts_root / "apply_error.txt").write_text(apply_msg, encoding="utf-8")

            pf = Path(patch_file) if patch_file else None
            try:
                pf_preview = pf.read_text(encoding="utf-8", errors="ignore") if pf and pf.exists() else ""
            except Exception:
                pf_preview = ""

            yield ndjson(
                {
                    "event": "coder_fallback",
                    "data": f"git apply failed (attempt {attempt + 1}): {apply_msg} {patch_file or ''}",
                }
            )

            debugger_prompt = (
                f"git apply failed: {apply_msg}\n\n"
                f"{clean_diff}\n\n"
                f"File content for {patch_file}:\n{pf_preview}"
                f"Answer with the git diff i should apply \nGit diff:\n"
            )
            debug_chunks: List[str] = []
            for chunk in ask_stream(req.models.coder, DIFF_DEBUGGER_SYSTEM, debugger_prompt):
                debug_chunks.append(chunk)
                yield ndjson({"event": "coder_debug_chunk", "data": chunk[-EVENT_BUFFER_LIMIT:]})

            debug_diff = "".join(debug_chunks).strip()

            # If it doesn't start with a valid diff, try to extract fenced block
            if not debug_diff.startswith("diff --git"):
                logger.info("Not a diff format, Fallback to markdown.")
                clean_diff = extract_code_from_markdown(debug_diff, "diff") or ""
            else:
                clean_diff = debug_diff

            ok_apply, apply_msg, patch_file = git_apply(clean_diff, repo)
            if not ok_apply:
                (artifacts_root / "apply_error.txt").write_text(
                    apply_msg, encoding="utf-8"
                )
                last_err = f"git apply failed again on attempt {attempt + 1}: {apply_msg} {patch_file or ''}"
                yield ndjson({"event": "error", "data": f"git apply failed again: {apply_msg} {patch_file}"})
                break
        yield ndjson({"event": "patch_applied", "data": {"ok": True, "attempt": attempt + 1}})
        success = True
        break

    if not success:
        yield ndjson({"event": "error", "data": last_err or f"Coder failed after {max_coder_attempts} attempts"})
        return

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

    REPAIR_MAX = 3
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
        for chunk in ask_stream(req.models.critic, CRITIC_SYSTEM, critic_user):
            critic_chunks.append(chunk)
            yield ndjson({"event": "critic_chunk", "data": chunk[-EVENT_BUFFER_LIMIT:]})
        critic_diff = "".join(critic_chunks)
        (artifacts_root / "critic" / f"critic_{i + 1}.diff").write_text(critic_diff, encoding="utf-8")

        ok, msg, _ = validate_unified_diff(critic_diff, req.allow)
        if not ok:
            yield ndjson({"event": "error", "data": f"Critic diff invalid: {msg}"})
            return
        ok_apply, apply_msg, patch_file = git_apply(critic_diff, repo)
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


@overload
def run(req, *, as_iter: Literal[True]) -> Iterable[str]: ...
@overload
def run(req, *, as_iter: Literal[False] = ...) -> RunResult: ...

def run(req, *, as_iter: bool = False):
    """
    If as_iter=True: return a generator of NDJSON event lines.
    Otherwise: consume the stream and return a RunResult summary.
    """
    gen = _run_stream_iter(req)
    if as_iter:
        return gen

    # Eager consumption path
    events: List[str] = []
    ok = False
    artifacts_dir: Optional[str] = None
    last_error: Optional[str] = None

    for line in gen:
        events.append(line)
        # try to observe 'done' or 'error' to produce nicer summary
        try:
            evt = json.loads(line)
            if isinstance(evt, dict):
                if evt.get("event") == "error":
                    # last error seen
                    data = evt.get("data")
                    last_error = data if isinstance(data, str) else str(data)
                if evt.get("event") == "done":
                    data = evt.get("data") or {}
                    ok = bool(data.get("ok"))
                    artifacts_dir = data.get("artifacts_dir")
        except Exception:
            # ignore malformed NDJSON lines in summary mode
            pass

    return RunResult(ok=ok, artifacts_dir=artifacts_dir, last_error=last_error, events=events)

def run_stream(req) -> Iterable[str]:
    """Streaming alias kept for compatibility."""
    return _run_stream_iter(req)
