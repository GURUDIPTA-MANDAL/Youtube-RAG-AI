"""
STEP 3 — step3_build_embeddings.py  (v2 — faster embeddings)
Uses nomic-embed-text (3x faster than bge-m3) with larger batch sizes.
Includes skip logic to avoid re-embedding already processed videos.
"""

import os
import json
import time
import joblib
import numpy as np
import pandas as pd
import requests
from typing import Optional


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL     = os.getenv("EMBED_MODEL", "nomic-embed-text")


def create_embedding(text_list: list[str]) -> list[list[float]]:
    """Call Ollama /api/embed and return embedding vectors."""
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": text_list},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["embeddings"]


def build_embeddings(
    chunks_path: str,
    output_path: str,
    batch_size:  int = 16,            # v2: larger batch = fewer API calls = faster
    playlist_id: Optional[str] = None,
    skip_existing: bool = True,       # v2: skip already embedded chunks
) -> pd.DataFrame:
    """
    Loads transcript chunks, generates embeddings, saves DataFrame.

    Args:
        chunks_path:   Path to all_chunks.json from Step 2
        output_path:   Where to save the .joblib file
        batch_size:    Chunks per Ollama API call (larger = faster)
        playlist_id:   Optional identifier stored in DataFrame
        skip_existing: If True and output_path exists, load and skip already done

    Returns:
        DataFrame with embedding column added
    """
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    # Filter out empty chunks (saves time)
    chunks = [c for c in chunks if len(c.get("text", "").strip()) > 10]
    print(f"Building embeddings for {len(chunks)} chunks using {EMBED_MODEL}...")

    # Load existing embeddings to skip already-done chunks
    existing_df = None
    if skip_existing and os.path.exists(output_path):
        existing_df = joblib.load(output_path)
        existing_texts = set(existing_df["text"].tolist())
        chunks = [c for c in chunks if c["text"] not in existing_texts]
        print(f"  Skipping {len(existing_df)} already embedded chunks")
        print(f"  Embedding {len(chunks)} new chunks...")

    if not chunks:
        print("Nothing new to embed!")
        return existing_df

    texts      = [c["text"] for c in chunks]
    embeddings = []
    start      = time.time()

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        pct   = round((i / len(texts)) * 100)
        print(f"  [{pct:3d}%] Embedding chunks {i+1}–{min(i+batch_size, len(texts))} / {len(texts)}")

        try:
            batch_embeddings = create_embedding(batch)
            embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"  ⚠ Error on batch {i}: {e}. Retrying...")
            time.sleep(3)
            batch_embeddings = create_embedding(batch)
            embeddings.extend(batch_embeddings)

    elapsed = time.time() - start
    print(f"\nEmbedded {len(chunks)} chunks in {elapsed:.1f}s "
          f"({elapsed/len(chunks):.2f}s per chunk)")

    # Build new DataFrame
    new_df = pd.DataFrame(chunks)
    new_df["embedding"]   = embeddings
    new_df["playlist_id"] = playlist_id or "default"

    # Merge with existing if any
    if existing_df is not None:
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    # Save
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    joblib.dump(final_df, output_path)

    print(f"Embeddings saved → {output_path}")
    print(f"Total chunks: {len(final_df)} | Embedding dim: {len(embeddings[0])}")
    return final_df


def load_embeddings(path: str) -> pd.DataFrame:
    return joblib.load(path)


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    df = build_embeddings(
        chunks_path = "./data/transcripts/all_chunks.json",
        output_path = "./data/embeddings/embeddings.joblib",
        batch_size  = 16,
    )
    print(f"\nSample:\n{df.iloc[0][['video_index','title','start','end','text']]}")