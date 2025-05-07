def note(user_input: str, content: str) -> str:
    if not content.strip():
        return "❌ I need something to note."
    with open("notes.txt", "a", encoding="utf-8") as f:
        f.write(f"- {content.strip()}\n")
    return f"📝 Got it. I noted: “{content.strip()}”."
