import importlib.util
from pathlib import Path
import re

TOOLS_DIR = Path(__file__).parent.parent / "tools"

def load_tools():
    _tools = []
    for file in TOOLS_DIR.glob("*.py"):
        if file.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(file.stem, file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        tool = {
            "name": getattr(module, "name", file.stem),
            "description": getattr(module, "description", ""),
            "pattern": getattr(module, "pattern", ""),
            "action": getattr(module, "action", None),
        }
        if callable(tool["action"]):
            _tools.append(tool)

    return _tools

def match_and_run_tools(user_input: str, tool_list: list) -> str | None:
    for tool in tool_list:
        match = re.search(tool["pattern"], user_input, re.IGNORECASE)
        if match:
            return tool["action"](user_input, **match.groupdict())
    return None
