name = "get_time"
description = "Tells the current time"
pattern = r"\bwhat('?s| is)?\b.*\btime\b"

def action():
    from datetime import datetime
    print(f"Current time: {datetime.now().strftime('%H:%M:%S')}")
