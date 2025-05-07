import re
import yaml
from pathlib import Path

INTENTS_PATH = Path(__file__).parent / "intents.yaml"

with open(INTENTS_PATH, "r", encoding="utf-8") as f:
    INTENT_REGISTRY = yaml.safe_load(f)

def detect_intent(user_input: str):
    for entry in INTENT_REGISTRY:
        pattern = entry["pattern"]
        match = re.search(pattern, user_input, re.IGNORECASE)
        if match:
            return {
                "intent": entry["intent"],
                "action": entry["action"],
                "params": match.groupdict()
            }
    return {"intent": None, "action": None, "params": {}}
