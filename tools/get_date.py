name = "get_date"
description = "Tells the current date"
pattern = r"\bwhat('?s| is)?\b.*\bdate\b"

def action():
    from datetime import datetime
    print(f"Today is: {datetime.now().strftime('%Y-%m-%d')}")
