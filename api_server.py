import tempfile
from pathlib import Path

import os
import whisper
from fastapi import FastAPI, Header, HTTPException, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from engine.engine_config import load_settings, save_settings
from engine.agent_core import handle_input
from engine.api_key_store import load_valid_api_keys
from engine.di import container
from engine.conversation_store import (
    create_new_conversation,
    load_conversation,
    save_conversation, list_conversation_meta
)
from engine.interfaces import VectorStoreManagerInterface
from engine.utils import load_metadata
from engine.user_manager import UserManager

# Export the vectorstore_manager instance for direct imports
vectorstore_manager = container.get_typed("vectorstore_manager", VectorStoreManagerInterface)

# Create UserManager instance
user_manager = UserManager()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
asset_path = Path(__file__).parent / "assets"
app.mount("/assets", StaticFiles(directory=asset_path), name="assets")

settings = load_settings()
model = whisper.load_model("base")

def verify_api_key(x_api_key: str = Header(...)):
    valid_keys = load_valid_api_keys()
    if x_api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API Key")


class QueryRequest(BaseModel):
    input: str
    backend: str = "ollama"
    conversation_id: str
    mode: str | None = None
    project_path: str | None = None

class SettingsUpdate(BaseModel):
    llm_backend: str | None = None
    llm_model: str | None = None
    openai_model: str | None = None
    voice: bool | None = None
    streaming: bool | None = None
    openai_api_key: str | None = None

class ProfileUpdate(BaseModel):
    name: str | None = None
    avatar: str | None = None

class PreferencesUpdate(BaseModel):
    preferred_language: str | None = None
    communication_style: str | None = None
    focus: str | None = None
    theme: str | None = None
    font_size: str | None = None
    notification_level: str | None = None
    timezone: str | None = None
    date_format: str | None = None
    time_format: str | None = None

class PersonalizationUpdate(BaseModel):
    interests: list[str] | None = None
    expertise: list[str] | None = None
    learning_goals: list[str] | None = None
    favorite_tools: list[str] | None = None
    custom_shortcuts: dict[str, str] | None = None

class PrivacyUpdate(BaseModel):
    share_conversations: bool | None = None
    allow_analytics: bool | None = None
    store_history: bool | None = None

@app.post("/query")
def query(req: QueryRequest, _: str = Depends(verify_api_key)):
    profile = load_conversation(req.conversation_id)
    reply = handle_input(req.input, req.backend, profile, settings)
    save_conversation(req.conversation_id, profile)
    return {"response": reply}

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        contents = await audio.read()
        tmp.write(contents)
        tmp.flush()
        try:
            result = model.transcribe(tmp.name)
        except Exception:
            return {"text": "[transcription failed]"}
    return {"text": result["text"]}

@app.post("/query/stream")
def query_stream(req: QueryRequest, _: str = Depends(verify_api_key)):
    profile = load_conversation(req.conversation_id)
    generator = handle_input(req.input, req.backend, profile, settings, force_stream=True)
    save_conversation(req.conversation_id, profile)
    return StreamingResponse(generator, media_type="text/plain")

@app.get("/conversations")
def get_conversations():
    return list_conversation_meta()

@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    profile = load_conversation(conversation_id)
    if profile is not None and "project_path" in profile:
        profile["project_metadata"] = load_metadata(profile["project_path"])
    return profile


@app.post("/conversations/{conversation_id}")
def post_conversation(conversation_id: str, req: QueryRequest, _: str = Depends(verify_api_key)):
    profile = load_conversation(req.conversation_id)

    if req.mode:
        profile["mode"] = req.mode
    if req.project_path:
        profile["project_path"] = req.project_path
        profile["mode"] = "development"
        vectorstore_manager.get_vectorstore(profile)

        # Update recent projects in settings
        try:
            settings_path = Path("settings.json")
            settings_data = {}
            if settings_path.exists():
                import json
                with open(settings_path, "r") as f:
                    settings_data = json.load(f)

            # Add current project to recent projects
            recent_projects = settings_data.get("recent_projects", [])
            # Remove if already exists (to move it to the top)
            if req.project_path in recent_projects:
                recent_projects.remove(req.project_path)
            # Add to the beginning of the list
            recent_projects.insert(0, req.project_path)
            # Keep only the 10 most recent projects
            recent_projects = recent_projects[:10]
            settings_data["recent_projects"] = recent_projects

            # Save updated settings
            with open(settings_path, "w") as f:
                json.dump(settings_data, f, indent=2)
        except Exception:
            # Silently fail if we can't update settings
            pass

    # Get project metadata if available
    if profile is not None and "project_path" in profile:
        profile["project_metadata"] = load_metadata(profile["project_path"])

    save_conversation(conversation_id, profile)

    return {
        "conversation_id": conversation_id,
        "mode": profile["mode"],
        "project_path": profile["project_path"],
        "project_metadata": profile["project_metadata"]
    }

@app.post("/conversations/new")
def new_conversation():
    return {"conversation_id": create_new_conversation()}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/browse-folders")
def browse_folders(path: str = ""):
    if not path:
        # Use the root drive as the base folder
        current_drive = os.path.splitdrive(os.getcwd())[0]
        if current_drive:  # On Windows, this will be something like "C:"
            target = Path(current_drive + "\\")
        else:  # On non-Windows systems, fallback to root
            target = Path("/")
    else:
        # If a path is provided, use it directly
        try:
            target_path = Path(path)
            # Check if it's an absolute path
            if target_path.is_absolute():
                target = target_path
            else:
                # For relative paths, use the current directory as base
                target = Path("./").resolve() / path
            target = target.resolve()
        except Exception:
            raise HTTPException(400, "Invalid path format")

    if not target.exists() or not target.is_dir():
        raise HTTPException(400, "Invalid path")

    # Get parent path for breadcrumb navigation
    # For root drives (like C:\), there's no parent to navigate to
    is_root_drive = target == Path(os.path.splitdrive(str(target))[0] + "\\") if os.name == 'nt' else target == Path("/")
    parent_path = str(target.parent) if not is_root_drive else None

    # Get path parts for breadcrumb navigation
    path_parts = []
    current = target
    # Continue until we reach the root of the file system
    while True:
        # Add the current path part
        path_parts.insert(0, {"name": current.name or current.drive, "path": str(current)})

        # Stop if we've reached the root
        if current == current.parent or current == Path("/") or (os.name == 'nt' and current == Path(current.drive + "\\")):
            break

        # Move up to the parent
        current = current.parent

    # Get subdirectories with additional metadata
    subdirs = []
    for f in target.iterdir():
        if f.is_dir():
            # Check if directory contains project files (like .git, pyproject.toml, etc.)
            is_project = any(
                (f / marker).exists()
                for marker in [".git", "pyproject.toml", "package.json", "requirements.txt"]
            )

            # Get last modified time
            try:
                modified = f.stat().st_mtime
            except:
                modified = 0

            subdirs.append({
                "name": f.name,
                "path": str(f),
                "is_project": is_project,
                "modified": modified
            })

    # Sort directories: projects first, then alphabetically
    subdirs.sort(key=lambda x: (not x["is_project"], x["name"].lower()))

    # Get recent projects from settings if available
    recent_projects = []
    try:
        settings_path = Path("settings.json")
        if settings_path.exists():
            import json
            with open(settings_path, "r") as f:
                settings_data = json.load(f)
                recent_projects = settings_data.get("recent_projects", [])
    except:
        pass

    return {
        "current": str(target),
        "parent": parent_path,
        "path_parts": path_parts,
        "subfolders": subdirs,
        "separator": os.sep,
        "recent_projects": recent_projects
    }

@app.get("/settings")
def get_settings():
    """
    Get the current settings and available LLM options.

    Returns:
        Dictionary containing the current settings and available LLM options
    """
    current_settings = load_settings()

    # Define available LLM options
    llm_options = {
        "ollama": [
            "llama3",
            "llama2",
            "mistral",
            "codellama",
            "phi",
            "gemma"
        ],
        "openai": [
            "gpt-3.5-turbo",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o"
        ]
    }

    return {
        "settings": current_settings,
        "llm_options": llm_options
    }

@app.post("/settings")
def update_settings(settings_update: SettingsUpdate):
    """
    Update the settings with the provided values.

    Args:
        settings_update: SettingsUpdate model containing the settings to update

    Returns:
        Dictionary containing the updated settings
    """
    current_settings = load_settings()

    # Update the settings with the provided values
    update_dict = settings_update.dict(exclude_unset=True, exclude_none=True)
    for key, value in update_dict.items():
        current_settings[key] = value

    # Save the updated settings
    save_settings(current_settings)

    return {"settings": current_settings}

@app.get("/profile/{user_id}")
def get_profile(user_id: str, _: str = Depends(verify_api_key)):
    """
    Get a user's profile information.

    Args:
        user_id: User ID to get profile for

    Returns:
        Dictionary containing the user's profile information
    """
    profile = user_manager.get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    return {"profile": profile}

@app.post("/profile/{user_id}")
def update_profile(user_id: str, profile_update: ProfileUpdate, _: str = Depends(verify_api_key)):
    """
    Update a user's profile information.

    Args:
        user_id: User ID to update profile for
        profile_update: ProfileUpdate model containing the profile updates

    Returns:
        Dictionary containing the updated profile information
    """
    profile = user_manager.get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    # Update only the specified fields
    update_dict = profile_update.dict(exclude_unset=True, exclude_none=True)
    for key, value in update_dict.items():
        profile[key] = value

    success = user_manager.save_profile(user_id, profile)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save profile")

    return {"profile": profile}

@app.get("/profile/{user_id}/preferences")
def get_preferences(user_id: str, _: str = Depends(verify_api_key)):
    """
    Get a user's preferences.

    Args:
        user_id: User ID to get preferences for

    Returns:
        Dictionary containing the user's preferences
    """
    preferences = user_manager.get_preferences(user_id)
    if not preferences:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    return {"preferences": preferences}

@app.post("/profile/{user_id}/preferences")
def update_preferences(user_id: str, preferences_update: PreferencesUpdate, _: str = Depends(verify_api_key)):
    """
    Update a user's preferences.

    Args:
        user_id: User ID to update preferences for
        preferences_update: PreferencesUpdate model containing the preference updates

    Returns:
        Dictionary containing the updated preferences
    """
    # Update only the specified preferences
    update_dict = preferences_update.dict(exclude_unset=True, exclude_none=True)
    success = user_manager.update_preferences(user_id, update_dict)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update preferences")

    return {"preferences": user_manager.get_preferences(user_id)}

@app.get("/profile/{user_id}/personalization")
def get_personalization(user_id: str, _: str = Depends(verify_api_key)):
    """
    Get a user's personalization settings.

    Args:
        user_id: User ID to get personalization settings for

    Returns:
        Dictionary containing the user's personalization settings
    """
    personalization = user_manager.get_personalization(user_id)
    if not personalization:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    return {"personalization": personalization}

@app.post("/profile/{user_id}/personalization")
def update_personalization(user_id: str, personalization_update: PersonalizationUpdate, _: str = Depends(verify_api_key)):
    """
    Update a user's personalization settings.

    Args:
        user_id: User ID to update personalization settings for
        personalization_update: PersonalizationUpdate model containing the personalization updates

    Returns:
        Dictionary containing the updated personalization settings
    """
    # Update only the specified personalization settings
    update_dict = personalization_update.dict(exclude_unset=True, exclude_none=True)
    success = user_manager.update_personalization(user_id, update_dict)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update personalization settings")

    return {"personalization": user_manager.get_personalization(user_id)}

@app.get("/profile/{user_id}/privacy")
def get_privacy_settings(user_id: str, _: str = Depends(verify_api_key)):
    """
    Get a user's privacy settings.

    Args:
        user_id: User ID to get privacy settings for

    Returns:
        Dictionary containing the user's privacy settings
    """
    privacy_settings = user_manager.get_privacy_settings(user_id)
    if not privacy_settings:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    return {"privacy": privacy_settings}

@app.post("/profile/{user_id}/privacy")
def update_privacy_settings(user_id: str, privacy_update: PrivacyUpdate, _: str = Depends(verify_api_key)):
    """
    Update a user's privacy settings.

    Args:
        user_id: User ID to update privacy settings for
        privacy_update: PrivacyUpdate model containing the privacy setting updates

    Returns:
        Dictionary containing the updated privacy settings
    """
    # Update only the specified privacy settings
    update_dict = privacy_update.dict(exclude_unset=True, exclude_none=True)
    success = user_manager.update_privacy_settings(user_id, update_dict)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update privacy settings")

    return {"privacy": user_manager.get_privacy_settings(user_id)}

@app.get("/users")
def list_users(_: str = Depends(verify_api_key)):
    """
    List all users in the system.

    Returns:
        List of dictionaries containing user information
    """
    users = user_manager.list_users()
    return {"users": users}

@app.get("/health")
def health():
    return {"status": "ok"}

def main():
    """Main entry point for the API server."""
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run("api_server:app", host="127.0.0.1", port=args.port, reload=False)

if __name__ == "__main__":
    main()
