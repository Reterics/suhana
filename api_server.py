import tempfile
from pathlib import Path

import os
import whisper
from fastapi import FastAPI, Header, HTTPException, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from engine.engine_config import load_settings
from engine.agent_core import handle_input
from engine.api_key_store import load_valid_api_keys
from engine.di import container
from engine.conversation_store import (
    create_new_conversation,
    load_conversation,
    save_conversation, list_conversation_meta
)
from engine.interfaces import VectorStoreManagerInterface

# Export the vectorstore_manager instance for direct imports
vectorstore_manager = container.get_typed("vectorstore_manager", VectorStoreManagerInterface)

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
    return load_conversation(conversation_id)

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
    project_metadata = vectorstore_manager.project_metadata

    return {
        "conversation_id": conversation_id,
        "mode": profile["mode"],
        "project_path": profile["project_path"],
        "project_metadata": project_metadata
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

def main():
    """Main entry point for the API server."""
    import uvicorn
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=False)

if __name__ == "__main__":
    main()
