import os
import json
import shutil
from engine.agent import run_agent
from engine.profile import default_profile

def ensure_file(file_path, template_path=None, default_data=None):
    if not os.path.exists(file_path):
        if template_path and os.path.exists(template_path):
            shutil.copy(template_path, file_path)
            print(f"✅ Created {file_path} from template.")
        elif default_data is not None:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=2)
            print(f"✅ Created {file_path} with defaults.")
        else:
            print(f"⚠️  {file_path} missing and no template/default available.")

def main():
    ensure_file("settings.json", template_path="settings.template.json")
    ensure_file("profile.json", default_data=default_profile)
    run_agent()

if __name__ == "__main__":
    main()
