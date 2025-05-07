from actions.note import note
from actions.web_search import web_search
from actions.update_profile import update_profile
from actions.tell_time import tell_time
from actions.tell_date import tell_date

ACTION_MAP = {
    "note": note,
    "web_search": web_search,
    "update_profile": update_profile,
    "tell_time": tell_time,
    "tell_date": tell_date,
}

def execute_action(action_name: str, user_input: str, intent_data: dict):
    action = ACTION_MAP.get(action_name)
    if action:
        return action(user_input, **intent_data['params'])
    print(f"[⚠️] Unknown action: {action_name}")

