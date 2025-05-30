name = "get_date"
description = "Tells the current date"
pattern = r"\bwhat('?s| is)?\b.*\bdate\b"
from datetime import datetime

def action(user_input: str = None):
    return f"Today is: {datetime.now().strftime('%Y-%m-%d')}"
