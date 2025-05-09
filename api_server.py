import tempfile
from pathlib import Path

import whisper
from fastapi import FastAPI, Header, HTTPException, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.agent_core import handle_input
from engine.api_key_store import load_valid_api_keys
from engine.engine_config import load_settings
from engine.conversation_store import (
    create_new_conversation,
    list_conversations,
    load_conversation,
    save_conversation, list_conversation_meta
)

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

@app.post("/conversations/new")
def new_conversation():
    return {"conversation_id": create_new_conversation()}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=False)
