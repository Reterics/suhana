import toml
import re
import subprocess
import sys
import json
from pathlib import Path

PYPROJECT = Path("pyproject.toml")
TAURI_PACKAGE_JSON = Path("tauri-ui/package.json")
TAURI_CONF_JSON = Path("tauri-ui/src-tauri/tauri.conf.json")

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


def update_tauri_version(new_version):
    # Update package.json
    if TAURI_PACKAGE_JSON.exists():
        with open(TAURI_PACKAGE_JSON, "r", encoding="utf-8") as f:
            package_data = json.load(f)

        package_data["version"] = new_version

        with open(TAURI_PACKAGE_JSON, "w", encoding="utf-8") as f:
            json.dump(package_data, f, indent=2)
        print(f" tauri-ui/package.json updated to {new_version}")

    # Update tauri.conf.json
    if TAURI_CONF_JSON.exists():
        with open(TAURI_CONF_JSON, "r", encoding="utf-8") as f:
            tauri_conf_data = json.load(f)

        if "package" in tauri_conf_data:
            tauri_conf_data["package"]["version"] = new_version

            with open(TAURI_CONF_JSON, "w", encoding="utf-8") as f:
                json.dump(tauri_conf_data, f, indent=2)
            print(f" tauri-ui/src-tauri/tauri.conf.json updated to {new_version}")


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


def get_latest_git_tag():
    try:
        # Get the latest tag from git
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            stderr=subprocess.DEVNULL,
            universal_newlines=True
        ).strip()

        # Remove 'v' prefix if present
        if tag.startswith('v'):
            tag = tag[1:]

        return tag
    except subprocess.CalledProcessError:
        # No tags found
        return None

def get_current_version(data):
    # Get version from pyproject.toml
    file_version = None
    if "tool" in data and "poetry" in data["tool"]:
        file_version = data["tool"]["poetry"]["version"]
    elif "project" in data:
        file_version = data["project"]["version"]

    # Get version from git tags
    git_version = get_latest_git_tag()

    # If we have both versions, compare them and return the newer one
    if file_version and git_version:
        file_parts = list(map(int, file_version.split('.')))
        git_parts = list(map(int, git_version.split('.')))

        # Compare major, minor, patch versions
        for f, g in zip(file_parts, git_parts):
            if f > g:
                print(f" Using version from pyproject.toml: {file_version} (newer than git tag: {git_version})")
                return file_version
            elif g > f:
                print(f" Using version from git tag: {git_version} (newer than pyproject.toml: {file_version})")
                return git_version

        # If we get here, versions are equal
        print(f" Versions in pyproject.toml and git tag are the same: {file_version}")
        return file_version

    # Return whichever version we have, or None if neither exists
    if file_version:
        print(f" Using version from pyproject.toml: {file_version} (no git tag found)")
        return file_version
    elif git_version:
        print(f" Using version from git tag: {git_version} (no version in pyproject.toml)")
        return git_version
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
            print("Could not detect current version from pyproject.toml or git tags.")
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
    update_tauri_version(new_version)
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
