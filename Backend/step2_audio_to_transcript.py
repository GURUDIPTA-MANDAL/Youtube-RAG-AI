"""
STEP 2 — step2_audio_to_transcript.py  (CPU only)
Transcribes MP3s using faster-whisper on CPU.
Uses int8 quantization for maximum CPU speed.
"""

import os
import json
import time
from faster_whisper import WhisperModel


def get_whisper_model(model_size: str = "base") -> WhisperModel:
    """
    Load faster-whisper model for CPU.
    int8 = quantized, fastest on CPU.
    """
    print(f"Loading faster-whisper '{model_size}' on CPU...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    print("Model loaded ")
    return model


def transcribe_audio_files(
    audio_dir:          str,
    output_dir:         str,
    playlist_meta_path: str,
    model_size:         str = "base",
    chunk_seconds:      int = 60,
    use_gpu:            bool = False,   # ignored, always CPU
) -> list[dict]:
    """
    Transcribes every MP3 using faster-whisper (CPU) and saves chunked JSON.

    Args:
        audio_dir:          Folder containing MP3s
        output_dir:         Where to save transcript JSON files
        playlist_meta_path: Path to playlist_meta.json from Step 1
        model_size:         tiny / base / small / medium
        chunk_seconds:      Group transcript into N-second chunks
        use_gpu:            Ignored — always uses CPU

    Returns:
        List of chunk dicts with timestamps
    """
    os.makedirs(output_dir, exist_ok=True)

    with open(playlist_meta_path, "r", encoding="utf-8") as f:
        playlist = json.load(f)

    model       = get_whisper_model(model_size)
    all_chunks  = []
    total_start = time.time()

    for video in playlist:
        mp3_path = video["filepath"]

        if not os.path.exists(mp3_path):
            print(f"  ⚠ Skipping (not found): {mp3_path}")
            continue

        print(f"\nTranscribing [{video['index']}] {video['title'][:60]} ...")
        t0 = time.time()

        # Transcribe on CPU with faster-whisper
        segments, info = model.transcribe(
            mp3_path,
            word_timestamps=False,   # faster without word-level timestamps
            vad_filter=True,         # skip silent parts automatically
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
            language=None,           # auto-detect language
        )

        # Convert lazy generator to list
        seg_list = list(segments)
        elapsed  = time.time() - t0
        print(f"  Done in {elapsed:.1f}s | lang={info.language} | {len(seg_list)} segments")

        # Group into fixed-size chunks
        chunks       = _group_into_chunks(seg_list, chunk_seconds)
        video_chunks = []

        for chunk in chunks:
            video_chunks.append({
                "video_index": video["index"],
                "video_id":    video["video_id"],
                "title":       video["title"],
                "url":         video["url"],
                "start":       round(chunk["start"], 1),
                "end":         round(chunk["end"], 1),
                "text":        chunk["text"].strip(),
            })

        # Save per-video transcript
        out_path = os.path.join(
            output_dir, f"{video['index']}_{video['video_id']}.json"
        )
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(video_chunks, f, indent=2, ensure_ascii=False)

        all_chunks.extend(video_chunks)
        print(f"  → {len(video_chunks)} chunks saved")

    # Save combined transcript for the whole playlist
    combined_path = os.path.join(output_dir, "all_chunks.json")
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    total = time.time() - total_start
    print(f"\n Done! {len(all_chunks)} chunks in {total:.1f}s → {combined_path}")
    return all_chunks


def _group_into_chunks(segments, chunk_seconds: int) -> list[dict]:
    """Merge faster-whisper segments into fixed-duration chunks."""
    if not segments:
        return []

    chunks    = []
    buf_text  = []
    buf_start = segments[0].start
    buf_end   = segments[0].end

    for seg in segments:
        if seg.start - buf_start >= chunk_seconds and buf_text:
            chunks.append({
                "start": buf_start,
                "end":   buf_end,
                "text":  " ".join(buf_text),
            })
            buf_text  = []
            buf_start = seg.start

        buf_text.append(seg.text.strip())
        buf_end = seg.end

    # Last chunk
    if buf_text:
        chunks.append({
            "start": buf_start,
            "end":   buf_end,
            "text":  " ".join(buf_text),
        })

    return chunks


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    chunks = transcribe_audio_files(
        audio_dir          = "./data/audio",
        output_dir         = "./data/transcripts",
        playlist_meta_path = "./data/audio/playlist_meta.json",
        model_size         = "base",
        chunk_seconds      = 60,
    )
    if chunks:
        print(f"\nSample chunk:\n{json.dumps(chunks[0], indent=2)}")
