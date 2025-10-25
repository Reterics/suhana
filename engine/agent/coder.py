from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Tuple

from engine.agent.commons import now_stamp
from engine.utils import configure_logging

logger = configure_logging(__name__)

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
7) No brace juggling, no duplicates, no invented context.

Answer with only the diff generated for this project..
"""

DIFF_DEBUGGER_SYSTEM = """
You are the CODER.
please answer with the fixed Diff according to the user input.
No comments, no messages, just the code to git apply --index -p0
"""


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


def git_apply(diff_text: str, repo_root: Path) -> tuple[bool, str, Path]:
    patch_file = repo_root / f".agent_patch_{now_stamp()}.diff"
    logger.info(f"Write git diff into {patch_file}")
    patch_file.write_text(diff_text, encoding="utf-8")

    cmd = ["git", "-C", str(repo_root), "apply", "--whitespace=fix", str(patch_file)]
    logger.info(f"Execute: {' '.join(cmd)}")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return True, "applied", patch_file
    return False, (proc.stderr or proc.stdout), patch_file

