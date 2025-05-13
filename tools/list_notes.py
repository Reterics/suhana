from pathlib import Path

name = "list_notes"
description = "Lists all stored notes by date"
pattern = r"\b(list|show|recall)\b.*\bnotes?\b"

def action() -> str:
    notes_dir = Path("knowledge/notes")
    files = sorted(notes_dir.glob("*.md"))
    if not files:
        return "📭 No notes found."

    out = ["🗒️ Your notes:"]
    for f in files[-5:]:  # show only latest 5 files
        out.append(f"- {f.name}")
    return "\n".join(out)
