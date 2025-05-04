from fastapi import FastAPI
from pydantic import BaseModel
from engine.profile import load_profile
from engine.engine_config import load_settings
from engine.agent_core import handle_input

app = FastAPI()
profile = load_profile()
settings = load_settings()

class QueryRequest(BaseModel):
    input: str
    backend: str = "ollama"

@app.post("/query")
def query(req: QueryRequest):
    reply = handle_input(req.input, req.backend, profile, settings)
    return {"response": reply}
