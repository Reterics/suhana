import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List

from engine.utils import configure_logging

logger = configure_logging(__name__)

LANG_BY_EXT = {
    ".ts": "ts", ".tsx": "tsx", ".php": "php", ".js": "js", ".jsx": "jsx", ".py": "py", ".json": "json"
}
EXCLUDED_DIRS = {
    "venv", ".venv", "env", ".env",
    "node_modules", "bower_components",
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache",
    "dist", "build", "out", ".next", ".turbo",
    ".idea", ".vscode", ".DS_Store",
    "vectorstore", ".agent_artifacts"
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

def collect_snippets(
    repo_root: Path,
    impacted: List[Dict[str, Any]],
    context_lines: int = 160,
    full_fallback_cap_lines: int = 2000,
) -> str:
    """
    Collect context snippets for CODER.
    Guarantees at least one excerpt per impacted file.
    - If symbols are provided and matched: capture up to 2 matches per symbol, centered with context.
    - If symbols are provided but no match: FALL BACK to a bounded full-file excerpt (first N lines).
    - If no symbols: include a bounded full-file excerpt (first N lines).
    """
    blocks: List[str] = []
    for item in impacted:
        rel = item.get("path")
        if not rel:
            continue
        p = repo_root / rel
        if not p.exists():
            # File might be created in this change; no snippet to send.
            logger.debug(f"[snippets] Skipping missing file (likely 'add'): {rel}")
            continue

        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"[snippets] Failed to read {rel}: {e}")
            continue

        lines = text.splitlines()
        symbols: List[str] = (item.get("symbols") or [])

        added_any = False
        if symbols:
            for sym in symbols[:4]:
                # Use symbol name after optional Class#method and strip trailing ()
                needle = re.escape(sym.split("#")[-1].rstrip("()"))
                matches = list(re.finditer(needle, text))
                if not matches:
                    continue
                for m in matches[:2]:
                    line_no = text[: m.start()].count("\n") + 1
                    start = max(1, line_no - context_lines // 2)
                    end = min(len(lines), line_no + context_lines // 2)
                    blocks.append(read_excerpt(p, start, end))
                    added_any = True

        # Fallbacks to ensure CODER sees something for this file
        if not symbols or not added_any:
            cap = min(len(lines), max(context_lines, full_fallback_cap_lines))
            # Prefer a bounded "full-file" window from the beginning to keep token usage reasonable
            blocks.append(read_excerpt(p, 1, cap))
            if symbols and not added_any:
                logger.debug(f"[snippets] Fallback to bounded full-file excerpt for {rel} (no symbol matches)")

    return "\n\n=====\n\n".join(blocks)
