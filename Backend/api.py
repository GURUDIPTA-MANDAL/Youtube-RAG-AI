"""
STEP 5 — api.py  (v2 — faster indexing with skip logic)
FastAPI REST API powering the Chrome extension.

Key improvements:
  - Skips already-indexed videos (no re-processing)
  - Uses faster-whisper + nomic-embed-text
  - Larger embedding batches
  - Better progress reporting

Run:
  uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import json
import joblib
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from step1_video_to_audio      import download_playlist_audio
from step2_audio_to_transcript import transcribe_audio_files
from step3_build_embeddings    import build_embeddings
from step4_search_engine       import search, EmbeddingStore

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

API_KEY       = os.getenv("API_KEY", "changeme")
DATA_DIR      = os.getenv("DATA_DIR", "./data")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
USE_GPU       = os.getenv("USE_GPU", "false").lower() == "true"

app = FastAPI(
    title="YouTube Playlist Search API v2",
    description="Fast RAG-powered semantic search over YouTube playlist transcripts",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store          = EmbeddingStore(data_dir=os.path.join(DATA_DIR, "embeddings"))
indexing_jobs: dict[str, dict] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────────────

class IndexRequest(BaseModel):
    playlist_url:  str
    playlist_id:   str
    whisper_model: str = WHISPER_MODEL
    chunk_seconds: int = 60
    use_gpu:       bool = USE_GPU

class SearchRequest(BaseModel):
    query:       str
    playlist_id: Optional[str] = None
    top_k:       int = 5

class SearchResult(BaseModel):
    video_index:   int
    video_id:      str
    title:         str
    url:           str
    start:         float
    end:           float
    text:          str
    score:         float
    timestamp_url: str

class SearchResponse(BaseModel):
    answer:  str
    results: list[SearchResult]


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────

def require_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ─────────────────────────────────────────────────────────────────────────────
# Background pipeline
# ─────────────────────────────────────────────────────────────────────────────

def _run_indexing_pipeline(req: IndexRequest):
    pid = req.playlist_id

    try:
        audio_dir      = os.path.join(DATA_DIR, "audio",       pid)
        transcript_dir = os.path.join(DATA_DIR, "transcripts", pid)
        embed_path     = os.path.join(DATA_DIR, "embeddings",  f"{pid}.joblib")

        def update(status, progress, msg=""):
            indexing_jobs[pid]["status"]   = status
            indexing_jobs[pid]["progress"] = progress
            indexing_jobs[pid]["message"]  = msg
            print(f"[{pid}] {status} {progress}% {msg}")

        # ── Step 1: Download ────────────────────────────────────────────────
        update("downloading", 5, "Downloading audio files in parallel...")
        meta_path = os.path.join(audio_dir, "playlist_meta.json")

        # Skip download if already done
        if os.path.exists(meta_path):
            update("downloading", 20, "Audio already downloaded, skipping...")
        else:
            download_playlist_audio(req.playlist_url, audio_dir)
            update("downloading", 20, "Download complete")

        # ── Step 2: Transcribe ──────────────────────────────────────────────
        combined_path = os.path.join(transcript_dir, "all_chunks.json")

        # Skip transcription if already done
        if os.path.exists(combined_path):
            update("transcribing", 55, "Transcripts already exist, skipping...")
        else:
            update("transcribing", 25, "Transcribing with faster-whisper...")
            transcribe_audio_files(
                audio_dir          = audio_dir,
                output_dir         = transcript_dir,
                playlist_meta_path = meta_path,
                model_size         = req.whisper_model,
                chunk_seconds      = req.chunk_seconds,
                use_gpu            = req.use_gpu,
            )
            update("transcribing", 55, "Transcription complete")

        # ── Step 3: Embed ───────────────────────────────────────────────────
        update("embedding", 60, "Building embeddings (skipping already done)...")
        df = build_embeddings(
            chunks_path    = combined_path,
            output_path    = embed_path,
            batch_size     = 16,
            playlist_id    = pid,
            skip_existing  = True,    # ← key speedup: skip already embedded
        )

        # ── Done ────────────────────────────────────────────────────────────
        store.save(df, playlist_id=pid)
        indexing_jobs[pid].update({
            "status":      "done",
            "progress":    100,
            "message":     f"Indexed {len(df)} chunks",
            "chunk_count": len(df),
            "finished_at": datetime.utcnow().isoformat(),
        })
        print(f"[{pid}] ✅ Done — {len(df)} chunks indexed")

    except Exception as e:
        indexing_jobs[pid]["status"]  = "error"
        indexing_jobs[pid]["error"]   = str(e)
        indexing_jobs[pid]["message"] = str(e)
        print(f"[{pid}] ❌ Error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/index")
def index_playlist(req: IndexRequest, background_tasks: BackgroundTasks,
                   x_api_key: str = Header(...)):
    require_api_key(x_api_key)

    pid = req.playlist_id

    # Don't re-index if in progress
    if pid in indexing_jobs and indexing_jobs[pid]["status"] not in ("done", "error"):
        return {"message": "Already indexing", "playlist_id": pid,
                "status": indexing_jobs[pid]["status"]}

    indexing_jobs[pid] = {
        "status":     "queued",
        "progress":   0,
        "message":    "Queued",
        "started_at": datetime.utcnow().isoformat(),
        "playlist_id": pid,
    }

    background_tasks.add_task(_run_indexing_pipeline, req)
    return {"message": "Indexing started", "playlist_id": pid, "poll_url": f"/status/{pid}"}


@app.get("/status/{playlist_id}")
def get_status(playlist_id: str, x_api_key: str = Header(...)):
    require_api_key(x_api_key)

    if playlist_id not in indexing_jobs:
        embed_path = os.path.join(DATA_DIR, "embeddings", f"{playlist_id}.joblib")
        if os.path.exists(embed_path):
            return {"status": "done", "playlist_id": playlist_id, "progress": 100}
        raise HTTPException(status_code=404, detail="Playlist not indexed")

    return indexing_jobs[playlist_id]


@app.post("/search", response_model=SearchResponse)
def search_playlist(req: SearchRequest, x_api_key: str = Header(...)):
    require_api_key(x_api_key)

    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        df = store.load(req.playlist_id) if req.playlist_id else store.all_data
        if df.empty:
            raise HTTPException(status_code=404, detail="No playlists indexed yet")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    result = search(req.query, df, top_k=req.top_k, playlist_id=req.playlist_id)
    return SearchResponse(**result)


@app.get("/playlists")
def list_playlists(x_api_key: str = Header(...)):
    require_api_key(x_api_key)

    embed_dir = os.path.join(DATA_DIR, "embeddings")
    playlists = []

    if os.path.isdir(embed_dir):
        for fname in os.listdir(embed_dir):
            if fname.endswith(".joblib"):
                pid = fname.replace(".joblib", "")
                df  = joblib.load(os.path.join(embed_dir, fname))
                playlists.append({
                    "playlist_id": pid,
                    "chunk_count": len(df),
                    "video_count": df["video_index"].nunique() if "video_index" in df.columns else "?",
                })

    return {"playlists": playlists}


@app.delete("/playlist/{playlist_id}")
def delete_playlist(playlist_id: str, x_api_key: str = Header(...)):
    """Delete a playlist's index to force re-indexing."""
    require_api_key(x_api_key)

    embed_path = os.path.join(DATA_DIR, "embeddings", f"{playlist_id}.joblib")
    if os.path.exists(embed_path):
        os.remove(embed_path)
        store.invalidate(playlist_id)
        return {"message": f"Deleted index for {playlist_id}"}
    raise HTTPException(status_code=404, detail="Playlist not found")


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)