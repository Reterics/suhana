name = "get_time"
description = "Tells the current time"
pattern = r"\bwhat('?s| is)?\b.*\btime\b"
from datetime import datetime

def action(user_input: str = None):
    return f"Current time: {datetime.now().strftime('%H:%M:%S')}"
