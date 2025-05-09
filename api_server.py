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
from engine.profile import load_profile

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
asset_path = Path(__file__).parent / "assets"
app.mount("/assets", StaticFiles(directory=asset_path), name="assets")

profile = load_profile()
settings = load_settings()
model = whisper.load_model("base")  # you can load this lazily too


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

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        contents = await audio.read()
        tmp.write(contents)
        tmp.flush()
        print(f"🔊 Received audio: {len(contents)} bytes")
        print(f"📄 Saved to: {tmp.name}")
        try:
            result = model.transcribe(tmp.name)
            print("✅ Whisper result:", result["text"])
        except Exception as e:
            print("❌ Whisper failed:", e)
            return {"text": "[transcription failed]"}
    return {"text": result["text"]}

@app.post("/query/stream")
def query_stream(req: QueryRequest, _: str = Depends(verify_api_key)):
    generator = handle_input(req.input, req.backend, profile, settings, force_stream=True)
    return StreamingResponse(generator, media_type="text/plain")

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 FastAPI starting...")
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=False)
