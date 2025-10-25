from typing import Any, Dict, List

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
class ModelConfig(BaseModel):
    planner: str
    coder: str
    critic: str

class RunRequest(BaseModel):
    repo: str
    ticket: str
    allow: List[str] = Field(default_factory=lambda: [
        "apps/**/src", "packages/**/src", "backend/**", "tests/**", "database/migrations/**"
    ])
    backend_name: str
    models: ModelConfig
    constraints: List[str] = Field(default_factory=list)
    timeout_sec: int = 900
    max_map: int = 1500
    profile: Dict[str, Any] = Field(default_factory=dict)
    settings: Dict[str, Any] = Field(default_factory=dict)

class CommandOutcome(BaseModel):
    name: str
    ok: bool
    code: int

class RunResponse(BaseModel):
    status: str
    artifacts_dir: str
    plan: Dict[str, Any]
    touched_files: List[str]
    logs: Dict[str, Any]
