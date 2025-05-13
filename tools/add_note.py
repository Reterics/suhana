from datetime import datetime
from pathlib import Path

name = "add_note"
description = "Add a personal note or reminder"
pattern = r"\b(remind|note|remember|todo)\b.*(?P<content>.+)"

def action(user_input: str, content: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    notes_path = Path("knowledge/notes") / f"{datetime.now().date()}.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write(f"- {timestamp} {content.strip()}\n")
    return f"Got it. I noted: “{content.strip()}”."
