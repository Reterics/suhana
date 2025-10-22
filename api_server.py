import json
import tempfile
from pathlib import Path

import os
from typing import List

try:
    import whisper  # optional, heavy dependency
except Exception:
    whisper = None  # allow importing api_server without whisper installed
from fastapi import FastAPI, Header, HTTPException, Depends, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fastapi import Depends, Header, Request
from fastapi.responses import StreamingResponse

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey, X25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from engine.backends.ollama import get_downloaded_models
from engine.crypto_query import b64d, derive_aes256_gcm, ndjson_encrypted_stream, b64u
from engine.settings_manager import SettingsManager
from engine.agent_core import handle_input
from engine.di import container
from engine.conversation_store import (
    DEFAULT_CATEGORY,
    conversation_store
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

# Initialize SettingsManager for per-user settings handling
settings_manager = SettingsManager()
# Lazy-load whisper model when used; keep import optional to avoid test-time failures
_model_whisper = None

def verify_api_key(x_api_key: str = Header(...), request: Request = None):
    """
    Verify the API key and extract the associated user ID.

    Args:
        x_api_key: API key from the request header
        request: FastAPI request object (for endpoint tracking)

    Returns:
        str: User ID associated with the API key

    Raises:
        HTTPException: If the API key is invalid or rate limit is exceeded
    """
    from engine.api_key_store import get_api_key_manager

    # Get the endpoint path for tracking
    endpoint = request.url.path if request else None

    # Validate the API key
    api_key_manager = get_api_key_manager()
    is_valid, user_id, error_message = api_key_manager.validate_key(x_api_key, endpoint)

    if not is_valid:
        if error_message == "Rate limit exceeded":
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        else:
            raise HTTPException(status_code=401, detail=error_message or "Invalid API Key")

    return user_id


def verify_or_guest(x_api_key: str | None = Header(default=None, alias="x-api-key"), request: Request = None):
    """
    Verify API key if present; otherwise, allow a public guest user id for non-secure endpoints.
    """
    # If no API key provided, return a shared guest identity
    if x_api_key is None:
        return "guest_public"
    # Else validate normally
    return verify_api_key(x_api_key, request)


class QueryRequest(BaseModel):
    input: str | None = None
    backend: str = "ollama"
    conversation_id: str | None = None
    mode: str | None = None
    project_path: str | None = None

class SettingsUpdate(BaseModel):
    llm_backend: str | None = None
    llm_model: str | None = None
    openai_model: str | None = None
    voice: bool | None = None
    streaming: bool | None = None
    secured_streaming: bool | None = None
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

class NewConversationRequest(BaseModel):
    category: str = DEFAULT_CATEGORY
    input: str | None = None
    conversation_id: str | None = None

class UserRegistration(BaseModel):
    username: str
    password: str
    name: str | None = None
    role: str = "user"

class UserLogin(BaseModel):
    username: str
    password: str

def _get_conversation_profile(conversation_id: str, user_id: str):
    """
    Get or create a conversation profile.

    Args:
        conversation_id: ID of the conversation to get or create
        user_id: User ID from the API key

    Returns:
        Tuple of (conversation_id, profile)
    """
    # Normalize empty or whitespace-only IDs to None to avoid DB PK collisions
    if isinstance(conversation_id, str) and not conversation_id.strip():
        conversation_id = None

    # If conversation_id is not provided, create a new conversation
    if conversation_id is None:
        conversation_id = conversation_store.create_new_conversation(user_id)
        # Initialize with empty profile to avoid 404 error
        profile = {"history": [], "user_id": user_id}
    else:
        profile = conversation_store.load_conversation(conversation_id, user_id)
        # If the client provided a conversation_id but it doesn't exist yet,
        # treat it as a new conversation and initialize it server-side.
        if profile is None:
            profile = {"history": [], "user_id": user_id}
            # Persist immediately so subsequent operations find it
            conversation_store.save_conversation(conversation_id, profile, user_id)

    # Add or verify user context in the conversation
    if "user_id" not in profile:
        profile["user_id"] = user_id
    elif profile["user_id"] != user_id:
        # Check if user has permission to access other users' conversations
        from engine.security.access_control import Permission, check_permission
        if not check_permission(user_id, Permission.VIEW_ALL_CONVERSATIONS, profile["user_id"]):
            raise HTTPException(status_code=403, detail="You don't have permission to access this conversation")

    # Ensure profile has a history field
    if "history" not in profile:
        profile["history"] = []

    return conversation_id, profile

@app.post("/query")
def query(req: QueryRequest, user_id: str = Depends(verify_or_guest)):
    # Get or create conversation profile
    req.conversation_id, profile = _get_conversation_profile(req.conversation_id, user_id)

    # If input is not provided, return the conversation without processing
    if req.input is None:
        return {"response": "No input provided", "conversation_id": req.conversation_id}

    # Load per-user settings for this request
    user_settings = settings_manager.get_settings(user_id)
    reply = handle_input(req.input, req.backend, profile, user_settings)
    conversation_store.save_conversation(req.conversation_id, profile, user_id)
    return {"response": reply, "conversation_id": req.conversation_id}

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    # Ensure whisper is available
    global _model_whisper
    if whisper is None:
        # Optional dependency not installed
        raise HTTPException(status_code=501, detail="Speech-to-text not available: whisper is not installed")

    # Lazy-load the model on first use
    if _model_whisper is None:
        try:
            _model_whisper = whisper.load_model("base")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load whisper model: {e}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        contents = await audio.read()
        tmp.write(contents)
        tmp.flush()
        try:
            result = _model_whisper.transcribe(tmp.name)
        except Exception:
            return {"text": "[transcription failed]"}
    return {"text": result.get("text", "")}

@app.post("/query/stream")
def query_stream(req: QueryRequest, user_id: str = Depends(verify_or_guest)):
    req.conversation_id, profile = _get_conversation_profile(req.conversation_id, user_id)
    if req.input is None:
        async def simple_generator():
            yield "No input provided"
        return StreamingResponse(simple_generator(), media_type="text/plain")

    user_settings = settings_manager.get_settings(user_id)
    generator = handle_input(req.input, req.backend, profile, user_settings, force_stream=True)

    def saving_generator():
        conversation_store.save_conversation(req.conversation_id, profile, user_id)  # save after user message
        try:
            for token in generator:
                yield token
        finally:
            conversation_store.save_conversation(req.conversation_id, profile, user_id)  # always save assistant part

    return StreamingResponse(saving_generator(), media_type="text/plain")

@app.post("/query/secure_stream")
async def query_stream(
    req: "QueryRequest",
    request: Request,
    user_id: str = Depends(verify_api_key),
    x_client_pubkey: str | None = Header(default=None, alias="X-Client-PubKey"),
):
    # keep your conversation/profile handling
    req.conversation_id, profile = _get_conversation_profile(req.conversation_id, user_id)

    # If client did not provide a pubkey, fall back to plaintext streaming for compatibility
    transport_encrypt = x_client_pubkey is not None

    if req.input is None:
        async def simple_generator():
            yield "No input provided"
        media_type = "application/x-ndjson" if transport_encrypt else "text/plain"
        return StreamingResponse(simple_generator(), media_type=media_type)

        # Your existing token generator (sync iterator)
    user_settings = settings_manager.get_settings(user_id)
    generator = handle_input(req.input, req.backend, profile, user_settings, force_stream=True)

    def saving_iter():
        # save after user message
        conversation_store.save_conversation(req.conversation_id, profile, user_id)
        try:
            for token in generator:
                yield token
        finally:
            # always save assistant part
            conversation_store.save_conversation(req.conversation_id, profile, user_id)

    if not transport_encrypt:
        # Original plaintext behavior
        return StreamingResponse(saving_iter(), media_type="text/plain")

    # --- Transport-layer encryption setup (server side) ---
    # 1) Parse client's ephemeral X25519 pubkey (raw 32 bytes in base64)
    client_raw = b64d(x_client_pubkey)
    client_pub = X25519PublicKey.from_public_bytes(client_raw)

    # 2) Generate server ephemeral key & derive shared secret
    server_priv = X25519PrivateKey.generate()
    server_pub_raw = server_priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)  # raw 32B
    shared = server_priv.exchange(client_pub)  # 32B shared secret

    aesgcm = derive_aes256_gcm(shared, req.conversation_id)

    async def encrypted_stream():
        # First line: send server's ephemeral pubkey so client can derive same AES key
        first = {"type": "server_pubkey", "pubkey": b64u(server_pub_raw)}
        yield json.dumps(first, separators=(",", ":")) + "\n"

        async for line in ndjson_encrypted_stream(
                req.conversation_id,
                saving_iter(),
                aesgcm,
                max_tokens=20,
                max_bytes=2048,
                max_delay_ms=40,
        ):
            yield line

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        # disables nginx proxy buffering:
        "X-Accel-Buffering": "no",
        # Keep the connection open
        "Connection": "keep-alive",
        # Optional: disables Chrome’s MIME sniffing that can delay display
        "X-Content-Type-Options": "nosniff",
        "Content-Encoding": "identity"
    }

    return StreamingResponse(encrypted_stream(), media_type="application/x-ndjson", headers=headers)

@app.get("/conversations")
def get_conversations(user_id: str = Depends(verify_api_key)):
    """
    Get a list of conversations for the current user.

    Args:
        user_id: User ID from the API key

    Returns:
        List of conversation metadata
    """
    from engine.security.access_control import Permission, check_permission
    import concurrent.futures

    # Check if user has permission to view all conversations
    if check_permission(user_id, Permission.VIEW_ALL_CONVERSATIONS):
        # Get all conversations from all users
        all_conversations = []
        conversation_ids = set()

        users = user_manager.list_users()

        # Function to get conversations for a user
        def get_user_conversations(user):
            user_conversations = conversation_store.list_conversation_meta(user["id"])
            for conversation in user_conversations:
                conversation["user_id"] = user["id"]
                conversation["user_name"] = user.get("name", user["id"])
            return user_conversations

        # Use ThreadPoolExecutor to process users concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Process users in batches to avoid creating too many threads
            batch_size = 10
            for i in range(0, len(users), batch_size):
                user_batch = users[i:i+batch_size]
                for user_convs in executor.map(get_user_conversations, user_batch):
                    for conv in user_convs:
                        conversation_ids.add(conv["id"])
                    all_conversations.extend(user_convs)

        return all_conversations
    else:
        # Get only the user's conversations
        return conversation_store.list_conversation_meta(user_id)

@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user_id: str = Depends(verify_api_key)):
    """
    Get a specific conversation.

    Args:
        conversation_id: ID of the conversation to get
        user_id: User ID from the API key

    Returns:
        Conversation data
    """

    # Check if the conversation exists using a more efficient approach
    # Load the conversation directly (it will use cache if available)
    profile = conversation_store.load_conversation(conversation_id, user_id)

    if profile is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Add project metadata if available and not already in the profile
    if "project_path" in profile and profile["project_path"] is not None and "project_metadata" not in profile:
        # Use a cache for project metadata to avoid loading it repeatedly
        project_path = profile["project_path"]
        # Create a simple in-memory cache for project metadata
        if not hasattr(get_conversation, '_project_metadata_cache'):
            get_conversation._project_metadata_cache = {}

        if project_path in get_conversation._project_metadata_cache and get_conversation._project_metadata_cache[project_path] is not None:
            profile["project_metadata"] = get_conversation._project_metadata_cache[project_path]
        else:
            metadata = load_metadata(project_path)
            if metadata is not None:
                get_conversation._project_metadata_cache[project_path] = metadata
                profile["project_metadata"] = metadata

    return profile


@app.post("/conversations/{conversation_id}")
def post_conversation(conversation_id: str, req: QueryRequest, user_id: str = Depends(verify_api_key)):
    """Update a conversation's properties."""
    profile = conversation_store.load_conversation(conversation_id, user_id)

    if profile is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Add or verify user context in the conversation
    if "user_id" not in profile:
        profile["user_id"] = user_id

    # Update conversation properties
    if req.mode:
        profile["mode"] = req.mode
    if req.project_path is not None and req.project_path != "":
        profile["project_path"] = req.project_path
        profile["mode"] = "development"
        vectorstore_manager.get_vectorstore(profile)

    # Process input if provided
    if req.input:
        conversation_store.save_conversation(conversation_id, profile, user_id)

        # Update recent projects in settings (per-user) using settings_manager
        try:
            if req.project_path:
                merged = settings_manager.get_settings(user_id)
                recent_projects = merged.get("recent_projects", [])
                if req.project_path in recent_projects:
                    recent_projects.remove(req.project_path)
                recent_projects.insert(0, req.project_path)
                recent_projects = recent_projects[:10]
                merged["recent_projects"] = recent_projects
                settings_manager.save_settings(merged, user_id)
        except Exception:
            # Silently fail if we can't update settings
            pass

    # Get project metadata if available
    if "project_path" in profile and profile["project_path"] is not None and "project_metadata" not in profile:
        # Use a cache for project metadata to avoid loading it repeatedly
        project_path = profile["project_path"]
        # Create a simple in-memory cache for project metadata
        if not hasattr(get_conversation, '_project_metadata_cache'):
            get_conversation._project_metadata_cache = {}

        if project_path in get_conversation._project_metadata_cache:
            profile["project_metadata"] = get_conversation._project_metadata_cache[project_path]
        else:
            metadata = load_metadata(project_path)
            if metadata is not None:
                get_conversation._project_metadata_cache[project_path] = metadata
                profile["project_metadata"] = metadata

    # Save the conversation with user context
    conversation_store.save_conversation(conversation_id, profile, user_id)

    return {
        "conversation_id": conversation_id,
        "user_id": profile["user_id"],
        "mode": profile["mode"],
        "project_path": profile.get("project_path"),
        "project_metadata": profile.get("project_metadata", None)
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/browse-folders")
def browse_folders(path: str = "", user_id: str = Depends(verify_api_key)):
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

    # Get recent projects from per-user settings via settings_manager
    recent_projects = []
    try:
        user_settings = settings_manager.get_settings(user_id)
        recent_projects = user_settings.get("recent_projects", [])
    except Exception:
        pass

    return {
        "current": str(target),
        "parent": parent_path,
        "path_parts": path_parts,
        "subfolders": subdirs,
        "separator": os.sep,
        "recent_projects": recent_projects
    }


@app.get("/settings/{user_id}")
def get_user_settings(user_id: str, _: str = Depends(verify_api_key)):
    """
    Get MERGED settings for a specific user (global + overrides).
    """
    current_settings = settings_manager.get_settings(user_id)

    llm_options = {
        "ollama": get_downloaded_models(),
        "openai": [
            "gpt-3.5-turbo",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o"
        ],
        "gemini": [
            "gemini-1.5-flash",
            "gemini-1.5-pro"
        ],
        "claude": [
            "claude-3-opus-20240229",
            "claude-3-5-sonnet-20240620"
        ]
    }
    return {"settings": current_settings, "llm_options": llm_options}


@app.post("/settings/{user_id}")
def update_user_settings(user_id: str, body: dict, auth_user_id: str = Depends(verify_api_key)):
    """
    Update settings for a specific user (only overrides are saved).
    Accepts either a flat payload (matching SettingsUpdate) or an AppSettings-like
    payload with a top-level "settings" object used by the Tauri UI.
    """
    # Enforce that callers can only update their own settings
    if auth_user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only update your own settings")

    # Load merged settings to apply partial update
    merged = settings_manager.get_settings(user_id)

    # Normalize incoming overrides
    overrides = {}
    try:
        if isinstance(body, dict):
            # If the UI sent { settings: {...}, llm_options: {...} }, take the nested object
            if "settings" in body and isinstance(body["settings"], dict):
                overrides = {k: v for k, v in body["settings"].items() if v is not None}
            else:
                # Assume a flat shape containing only the updatable keys
                overrides = {k: v for k, v in body.items() if v is not None}
    except Exception:
        # If anything goes wrong parsing the body, keep overrides empty to avoid accidental resets
        overrides = {}

    # Apply overrides onto the merged settings
    for key, value in overrides.items():
        merged[key] = value

    # Persist
    ok = settings_manager.save_settings(merged, user_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save user settings")

    return {"settings": merged}

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
def update_profile(user_id: str, profile_update: ProfileUpdate, auth_user_id: str = Depends(verify_api_key)):
    """
    Update a user's profile information.

    Args:
        user_id: User ID to update profile for
        profile_update: ProfileUpdate model containing the profile updates

    Returns:
        Dictionary containing the updated profile information
    """
    # Only allow users to update their own profile unless they have admin privileges
    if auth_user_id != user_id:
        from engine.security.access_control import Permission, check_permission
        if not check_permission(auth_user_id, Permission.MANAGE_USERS):
            raise HTTPException(status_code=403, detail="You can only update your own profile")

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
def update_preferences(user_id: str, preferences_update: PreferencesUpdate, auth_user_id: str = Depends(verify_api_key)):
    """
    Update a user's preferences.

    Args:
        user_id: User ID to update preferences for
        preferences_update: PreferencesUpdate model containing the preference updates

    Returns:
        Dictionary containing the updated preferences
    """
    # Only allow users to update their own preferences unless they have admin privileges
    if auth_user_id != user_id:
        from engine.security.access_control import Permission, check_permission
        if not check_permission(auth_user_id, Permission.MANAGE_USERS):
            raise HTTPException(status_code=403, detail="You can only update your own preferences")

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
def update_personalization(user_id: str, personalization_update: PersonalizationUpdate, auth_user_id: str = Depends(verify_api_key)):
    """
    Update a user's personalization settings.

    Args:
        user_id: User ID to update personalization settings for
        personalization_update: PersonalizationUpdate model containing the personalization updates

    Returns:
        Dictionary containing the updated personalization settings
    """
    # Only allow users to update their own personalization settings unless they have admin privileges
    if auth_user_id != user_id:
        from engine.security.access_control import Permission, check_permission
        if not check_permission(auth_user_id, Permission.MANAGE_USERS):
            raise HTTPException(status_code=403, detail="You can only update your own personalization settings")

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
def update_privacy_settings(user_id: str, privacy_update: PrivacyUpdate, auth_user_id: str = Depends(verify_api_key)):
    """
    Update a user's privacy settings.

    Args:
        user_id: User ID to update privacy settings for
        privacy_update: PrivacyUpdate model containing the privacy setting updates

    Returns:
        Dictionary containing the updated privacy settings
    """
    # Only allow users to update their own privacy settings unless they have admin privileges
    if auth_user_id != user_id:
        from engine.security.access_control import Permission, check_permission
        if not check_permission(auth_user_id, Permission.MANAGE_USERS):
            raise HTTPException(status_code=403, detail="You can only update your own privacy settings")

    # Update only the specified privacy settings
    update_dict = privacy_update.dict(exclude_unset=True, exclude_none=True)
    success = user_manager.update_privacy_settings(user_id, update_dict)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update privacy settings")

    return {"privacy": user_manager.get_privacy_settings(user_id)}

@app.get("/users")
def list_users(user_id: str = Depends(verify_api_key)):
    """
    List all users in the system.

    Args:
        user_id: User ID from the API key

    Returns:
        List of dictionaries containing user information
    """
    from engine.security.access_control import Permission, check_permission

    # Check if user has permission to view users
    if not check_permission(user_id, Permission.VIEW_USERS):
        raise HTTPException(status_code=403, detail="You don't have permission to view users")

    users = user_manager.list_users()
    return {"users": users}

@app.get("/health")
def health():
    return {"status": "ok"}

# API Key Management Endpoints

class ApiKeyCreate(BaseModel):
    name: str = None
    rate_limit: int = None
    permissions: List[str] = None

@app.get("/api-keys")
def list_api_keys(user_id: str = Depends(verify_api_key), request: Request = None):
    """
    List API keys for the current user.

    Args:
        user_id: User ID from the API key
        request: FastAPI request object

    Returns:
        List of API keys for the user
    """
    from engine.api_key_store import get_api_key_manager
    from engine.security.access_control import Permission, check_permission

    api_key_manager = get_api_key_manager()

    # Check if user has permission to view all API keys
    if check_permission(user_id, Permission.MANAGE_USERS):
        # Admin can request keys for any user
        requested_user = request.query_params.get("user_id", user_id) if request else user_id
        keys = api_key_manager.get_user_keys(requested_user)
        return {"keys": keys, "user_id": requested_user}
    else:
        # Regular users can only view their own keys
        keys = api_key_manager.get_user_keys(user_id)

        # Remove the actual key value for security (mask long keys only)
        for key in keys:
            if "key" in key:
                raw = key["key"]
                if isinstance(raw, str) and len(raw) > 12:
                    key["key"] = raw[:8] + "..." + raw[-4:]
                else:
                    key["key"] = raw

        return {"keys": keys, "user_id": user_id}

@app.post("/api-keys")
def create_api_key(key_data: ApiKeyCreate, user_id: str = Depends(verify_api_key)):
    """
    Create a new API key for the current user.

    Args:
        key_data: API key creation parameters
        user_id: User ID from the API key

    Returns:
        The newly created API key
    """
    from engine.api_key_store import get_api_key_manager, DEFAULT_RATE_LIMIT
    from engine.security.access_control import Permission, check_permission

    api_key_manager = get_api_key_manager()

    # Check if user has permission to create API keys
    if not check_permission(user_id, Permission.MANAGE_USERS):
        # Regular users can only create keys with default permissions
        permissions = ["user"]
        rate_limit = min(key_data.rate_limit or DEFAULT_RATE_LIMIT, DEFAULT_RATE_LIMIT)
    else:
        # Admins can create keys with custom permissions and rate limits
        permissions = key_data.permissions or ["user"]
        rate_limit = key_data.rate_limit or DEFAULT_RATE_LIMIT

    # Create the API key
    new_key = api_key_manager.create_api_key(
        user_id=user_id,
        name=key_data.name,
        rate_limit=rate_limit,
        permissions=permissions
    )

    return {
        "key": new_key,
        "name": key_data.name,
        "user_id": user_id,
        "rate_limit": rate_limit,
        "permissions": permissions
    }

@app.delete("/api-keys/{key}")
def revoke_api_key(key: str, user_id: str = Depends(verify_api_key)):
    """
    Revoke an API key.

    Args:
        key: The API key to revoke
        user_id: User ID from the API key

    Returns:
        Success status
    """
    from engine.api_key_store import get_api_key_manager
    from engine.security.access_control import Permission, check_permission

    api_key_manager = get_api_key_manager()

    # Get key info
    key_info = api_key_manager.get_key_info(key)

    if not key_info:
        raise HTTPException(status_code=404, detail="API key not found")

    # Check if user has permission to revoke this key
    if key_info["user_id"] != user_id and not check_permission(user_id, Permission.MANAGE_USERS):
        raise HTTPException(status_code=403, detail="You don't have permission to revoke this API key")

    # Revoke the key
    success = api_key_manager.revoke_api_key(key)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to revoke API key")

    return {"status": "success", "message": "API key revoked"}

@app.get("/api-keys/usage")
def get_api_key_usage(user_id: str = Depends(verify_api_key)):
    """
    Get API key usage statistics.

    Args:
        user_id: User ID from the API key

    Returns:
        API key usage statistics
    """
    from engine.api_key_store import get_api_key_manager
    from engine.security.access_control import Permission, check_permission

    api_key_manager = get_api_key_manager()

    # Check if user has permission to view all usage stats
    if check_permission(user_id, Permission.MANAGE_USERS):
        # Admin can view all usage stats
        stats = api_key_manager.get_usage_stats()
        return {"stats": stats}
    else:
        # Regular users can only view their own usage stats
        stats = api_key_manager.get_usage_stats(user_id=user_id)
        return {"stats": stats}

@app.post("/register")
def register_user(user_data: UserRegistration):
    """
    Register a new user and create an initial API key.

    Args:
        user_data: User registration data

    Returns:
        Dictionary containing the new user ID and API key
    """
    # Create the user
    success, message = user_manager.create_user(
        username=user_data.username,
        password=user_data.password,
        name=user_data.name,
        role=user_data.role
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Create an initial API key for the user
    from engine.api_key_store import get_api_key_manager, DEFAULT_RATE_LIMIT

    api_key_manager = get_api_key_manager()

    # Create the API key
    new_key = api_key_manager.create_api_key(
        user_id=user_data.username,
        name="Initial API Key",
        rate_limit=DEFAULT_RATE_LIMIT,
        permissions=["user"]
    )

    return {
        "user_id": user_data.username,
        "message": message,
        "api_key": new_key
    }

@app.post("/guest_login")
def guest_login():
    """
    Create or reuse a temporary Guest user and return an API key.

    Returns:
        Dictionary containing the guest user ID and API key
    """
    import secrets
    from engine.api_key_store import get_api_key_manager, DEFAULT_RATE_LIMIT
    from engine.security.access_control import Role, get_access_control_manager

    # Generate a simple guest username
    # Try a few times to avoid collision
    username = None
    for _ in range(5):
        candidate = f"guest_{secrets.token_hex(3)}"
        # If user exists, reuse that id; else create
        user = user_manager.db.get_user(candidate)
        if user:
            username = candidate
            break
        else:
            # Create guest user with random password
            pwd = secrets.token_urlsafe(8)
            ok, msg = user_manager.create_user(candidate, pwd, name="Guest", role="guest")
            if ok:
                username = candidate
                break
    if username is None:
        # Fallback: ensure some guest exists or raise
        raise HTTPException(status_code=500, detail="Failed to create guest user")

    # Ensure access control has this user as guest (in case it pre-existed)
    try:
        acm = get_access_control_manager()
        acm.set_user_role(username, Role.GUEST)
    except Exception:
        pass

    api_key_manager = get_api_key_manager()

    # Check if user already has an API key
    user_keys = api_key_manager.get_user_keys(username)
    if user_keys:
        api_key = user_keys[0]["key"]
    else:
        # Create a limited rate-limit key and mark permission as guest (informational)
        api_key = api_key_manager.create_api_key(
            user_id=username,
            name="Guest API Key",
            rate_limit=max(15, int(DEFAULT_RATE_LIMIT/2)),
            permissions=["guest"]
        )

    profile = user_manager.get_profile(username)
    return {
        "user_id": username,
        "api_key": api_key,
        "profile": profile
    }


@app.post("/login")
def login_user(user_data: UserLogin):
    """
    Authenticate a user and return an API key.

    Args:
        user_data: User login data

    Returns:
        Dictionary containing the user ID and API key
    """
    # Authenticate the user
    success, token = user_manager.authenticate(
        username=user_data.username,
        password=user_data.password
    )

    if not success:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Get or create an API key for the user
    from engine.api_key_store import get_api_key_manager, DEFAULT_RATE_LIMIT

    api_key_manager = get_api_key_manager()

    # Check if user already has an API key
    user_keys = api_key_manager.get_user_keys(user_data.username)

    if user_keys:
        # Use the first existing key
        api_key = user_keys[0]["key"]
    else:
        # Create a new API key
        api_key = api_key_manager.create_api_key(
            user_id=user_data.username,
            name="Login API Key",
            rate_limit=DEFAULT_RATE_LIMIT,
            permissions=["user"]
        )

    # Get user profile
    profile = user_manager.get_profile(user_data.username)

    return {
        "user_id": user_data.username,
        "api_key": api_key,
        "profile": profile
    }

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
