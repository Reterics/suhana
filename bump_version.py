import toml
import re
import subprocess
import sys
from pathlib import Path

PYPROJECT = Path("pyproject.toml")
if not PYPROJECT.exists():
    print(" pyproject.toml not found!")
    sys.exit(1)


def update_pyproject_version(new_version, data):
    if "tool" in data and "poetry" in data["tool"]:
        data["tool"]["poetry"]["version"] = new_version
    elif "project" in data:
        data["project"]["version"] = new_version
    else:
        print(" No [tool.poetry] or [project] version found in pyproject.toml.")
        sys.exit(1)
    with open(PYPROJECT, "w", encoding="utf-8") as f:
        toml.dump(data, f)
    print(f" pyproject.toml updated to {new_version}")


def update_in_file(path, new_version):
    if not Path(path).exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    content_new = re.sub(r'v\d+\.\d+\.\d+', f"v{new_version}", content)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content_new)
    print(f" {path} updated.")


def git_commit_and_tag(new_version):
    subprocess.check_call(["git", "add", "-u"])
    subprocess.check_call(["git", "commit", "-m", f"chore(release): prepare v{new_version}"])
    subprocess.check_call(["git", "tag", "-a", f"v{new_version}", "-m", f"chore(release): v{new_version}"])
    print(f" Git commit and tag v{new_version} created.")


def git_push(new_version):
    subprocess.check_call(["git", "push"])
    subprocess.check_call(["git", "push", "origin", f"v{new_version}"])
    print(" Changes and tag pushed to remote.")


def get_current_version(data):
    if "tool" in data and "poetry" in data["tool"]:
        return data["tool"]["poetry"]["version"]
    elif "project" in data:
        return data["project"]["version"]
    else:
        return None

def suggest_next_patch(version):
    parts = version.strip().split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    major, minor, patch = map(int, parts)
    return f"{major}.{minor}.{patch + 1}"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bump project version in pyproject.toml and tag release.")
    parser.add_argument("version", nargs="?", help="New version (format: x.y.z, e.g., 0.2.0)")
    args = parser.parse_args()
    data = toml.load(PYPROJECT)

    if args.version:
        new_version = args.version
    else:
        current_version = get_current_version(data)
        if not current_version:
            print("Could not detect current version from pyproject.toml.")
            sys.exit(1)
        suggestion = suggest_next_patch(current_version)
        prompt = f"Enter new version (x.y.z) [default: {suggestion}]: "
        inp = input(prompt).strip()
        new_version = inp if inp else suggestion
    if not re.match(r"^\d+\.\d+\.\d+$", new_version):
        print(" Version must be in x.y.z format (no 'v' prefix).")
        sys.exit(1)

    update_pyproject_version(new_version, data)
    update_in_file("README.md", new_version)
    update_in_file("settings.json", new_version)
    git_commit_and_tag(new_version)

    print(f"\n All done locally! You can review with:")
    print("   git log --oneline --decorate")
    print("   git tag")

    # Ask user if they want to push now
    do_push = input("\nWould you like to push the commit and tag to origin now? [y/N]: ").strip().lower()
    if do_push in ["y", "yes"]:
        git_push(new_version)
    else:
        print(" Not pushed. Remember to do it manually later:\n   git push && git push origin v" + new_version)


if __name__ == "__main__":
    main()
