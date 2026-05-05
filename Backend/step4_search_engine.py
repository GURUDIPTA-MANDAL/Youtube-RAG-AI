"""
STEP 4 — step4_search_engine.py  (v2)
RAG search: embed query → cosine similarity → LLM answer.
Uses nomic-embed-text by default (faster than bge-m3).
"""

import os
import requests
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics.pairwise import cosine_similarity
from typing import Optional


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL     = os.getenv("EMBED_MODEL", "nomic-embed-text")
LLM_MODEL       = os.getenv("LLM_MODEL", "llama3.2:3b")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _embed(text: str) -> list[float]:
    r = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": [text]},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["embeddings"][0]


def _llm_answer(prompt: str) -> str:
    r = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["response"].strip()


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


# ─────────────────────────────────────────────────────────────────────────────
# Main search
# ─────────────────────────────────────────────────────────────────────────────

def search(
    query:       str,
    df:          pd.DataFrame,
    top_k:       int = 5,
    playlist_id: Optional[str] = None,
) -> dict:
    """
    Full RAG pipeline: embed query → similarity search → LLM answer.

    Returns:
        {
          "answer":  "...",
          "results": [{video_index, video_id, title, url, start, end,
                       text, score, timestamp_url}, ...]
        }
    """
    # Filter by playlist
    search_df = df[df["playlist_id"] == playlist_id] if playlist_id else df
    if search_df.empty:
        return {"answer": "No indexed content found for this playlist.", "results": []}

    # 1. Embed query
    query_vec = np.array(_embed(query))

    # 2. Cosine similarity
    matrix      = np.vstack(search_df["embedding"].values)
    similarities = cosine_similarity([query_vec], matrix).flatten()

    # 3. Top-K results
    top_idx    = similarities.argsort()[::-1][:top_k]
    top_rows   = search_df.iloc[top_idx]
    top_scores = similarities[top_idx]

    # 4. Build results list
    results = []
    for (_, row), score in zip(top_rows.iterrows(), top_scores):
        start_sec = int(row["start"])
        results.append({
            "video_index":   int(row["video_index"]),
            "video_id":      row["video_id"],
            "title":         row["title"],
            "url":           row["url"],
            "start":         row["start"],
            "end":           row["end"],
            "text":          row["text"],
            "score":         round(float(score), 4),
            "timestamp_url": f"{row['url']}&t={start_sec}s",
        })

    # 5. Build RAG prompt
    context = "\n\n".join(
        f"[Video {r['video_index']} — \"{r['title']}\" at {_fmt_time(r['start'])}]\n{r['text']}"
        for r in results
    )

    prompt = f"""You are a helpful assistant searching through YouTube video transcripts.

QUERY: {query}

RELEVANT TRANSCRIPT SEGMENTS:
{context}

Based ONLY on the transcript segments above, give a concise answer.
For each piece of information, mention which video number and timestamp it came from.
If the answer is not in the transcripts, say so clearly."""

    # 6. LLM answer
    answer = _llm_answer(prompt)
    return {"answer": answer, "results": results}


# ─────────────────────────────────────────────────────────────────────────────
# Embedding store
# ─────────────────────────────────────────────────────────────────────────────

class EmbeddingStore:
    """Manages loading and in-memory caching of embedding DataFrames."""

    def __init__(self, data_dir: str = "./data/embeddings"):
        self.data_dir = data_dir
        self._cache: dict[str, pd.DataFrame] = {}

    def load(self, playlist_id: str = "default") -> pd.DataFrame:
        if playlist_id not in self._cache:
            path = os.path.join(self.data_dir, f"{playlist_id}.joblib")
            if not os.path.exists(path):
                path = os.path.join(self.data_dir, "embeddings.joblib")
            if not os.path.exists(path):
                raise FileNotFoundError(f"No embeddings found for: {playlist_id}")
            self._cache[playlist_id] = joblib.load(path)
        return self._cache[playlist_id]

    def save(self, df: pd.DataFrame, playlist_id: str = "default"):
        os.makedirs(self.data_dir, exist_ok=True)
        path = os.path.join(self.data_dir, f"{playlist_id}.joblib")
        joblib.dump(df, path)
        self._cache[playlist_id] = df

    def invalidate(self, playlist_id: str):
        self._cache.pop(playlist_id, None)

    @property
    def all_data(self) -> pd.DataFrame:
        frames = []
        if os.path.isdir(self.data_dir):
            for fname in os.listdir(self.data_dir):
                if fname.endswith(".joblib"):
                    frames.append(joblib.load(os.path.join(self.data_dir, fname)))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    df   = joblib.load("./data/embeddings/embeddings.joblib")
    q    = sys.argv[1] if len(sys.argv) > 1 else input("Ask: ").strip()
    resp = search(q, df, top_k=3)
    print(f"\nAnswer:\n{resp['answer']}\n")
    for r in resp["results"]:
        print(f"  Video {r['video_index']} | {_fmt_time(r['start'])} | {r['timestamp_url']}")