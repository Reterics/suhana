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
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from fastapi import HTTPException

from engine.agent.models import RunRequest, RunResponse, CommandOutcome
from engine.agent.coder import (
    CODER_SYSTEM,
    validate_unified_diff,
    git_apply,
    DIFF_DEBUGGER_SYSTEM,
    CmdResult,
    run_cmd,
)
from engine.agent.commons import (
    ask,
    ask_stream,
    extract_json_from_raw_text,
    extract_code_from_markdown,
    now_stamp,
)
from engine.agent.context import collect_snippets, build_repo_map
from engine.agent.planner import PLANNER_SYSTEM, get_planner_input
from engine.utils import configure_logging

logger = configure_logging(__name__)

CRITIC_SYSTEM = (
    "You are the CRITIC. Given the plan and failing outputs, return a SMALL unified diff fixing the root cause. No prose."
)

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

    plan_text = ask(req.models.planner, PLANNER_SYSTEM, planner_user)
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
    coder_diff = ask(req.models.coder, CODER_SYSTEM, coder_user)

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

    ok_apply, apply_msg, patch_file = git_apply(clean_diff, repo)
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
        critic_diff = ask(req.models.critic, CRITIC_SYSTEM, critic_user)
        (artifacts_root / "critic").mkdir(exist_ok=True)
        (artifacts_root / "critic" / f"critic_{i + 1}.diff").write_text(critic_diff, encoding="utf-8")

        ok, msg, _ = validate_unified_diff(critic_diff, req.allow)
        if not ok:
            raise HTTPException(400, f"Critic diff invalid: {msg}")
        ok_apply, apply_msg, patch_file = git_apply(critic_diff, repo)
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
            logger.info(f"Not a diff format, Fallback to markdown.")
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
                logger.info(f"Not a diff format, Fallback to markdown.")
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

