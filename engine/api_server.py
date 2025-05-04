from fastapi import FastAPI
from fastapi import Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from engine.profile import load_profile
from engine.engine_config import load_settings
from engine.agent_core import handle_input
from engine.api_key_store import load_valid_api_keys

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
profile = load_profile()
settings = load_settings()

def verify_api_key(x_api_key: str = Header(...)):
    valid_keys = load_valid_api_keys()  # dynamic load
    if x_api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API Key")


class QueryRequest(BaseModel):
    input: str
    backend: str = "ollama"

@app.post("/query")
def query(req: QueryRequest, _: str = Depends(verify_api_key)):
    reply = handle_input(req.input, req.backend, profile, settings)
    return {"response": reply}
