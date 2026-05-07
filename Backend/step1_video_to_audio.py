"""
STEP 1 — step1_video_to_audio.py  (v2 — parallel downloads)
Downloads all videos in a YouTube playlist as MP3 audio files.
Uses concurrent.futures to download multiple videos simultaneously.
"""

import os
import json
import time
import concurrent.futures
import yt_dlp


MAX_WORKERS = int(os.getenv("MAX_DOWNLOAD_WORKERS", 3))


def download_single_video(entry: dict, output_dir: str) -> dict | None:
    """
    Download audio for a single video entry.
    Returns metadata dict or None if failed.
    """
    if entry is None:
        return None

    video_id = entry.get("id", "")
    title    = entry.get("title", "Unknown")
    index    = entry.get("playlist_index", 0)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, f"{index}_{video_id}.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",    # 128kbps = smaller files, faster download
        }],
        "quiet": True,
        "ignoreerrors": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        mp3_path = os.path.join(output_dir, f"{index}_{video_id}.mp3")
        print(f"  ✅ [{index}] {title[:50]}")
        return {
            "index":    index,
            "video_id": video_id,
            "title":    title,
            "url":      f"https://www.youtube.com/watch?v={video_id}",
            "filepath": mp3_path,
        }

    except Exception as e:
        print(f"   [{index}] {title[:50]} — {e}")
        return None


def download_playlist_audio(playlist_url: str, output_dir: str) -> list[dict]:
    """
    Downloads all videos in a YouTube playlist as MP3 files in parallel.

    Args:
        playlist_url: Full YouTube playlist URL
        output_dir:   Folder where MP3s will be saved

    Returns:
        List of metadata dicts for successfully downloaded videos
    """
    os.makedirs(output_dir, exist_ok=True)

    # First: extract playlist metadata only (no download)
    print("Fetching playlist info...")
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
        info = ydl.extract_info(playlist_url, download=False)

    if "entries" not in info:
        raise ValueError("URL does not appear to be a YouTube playlist.")

    entries = [e for e in info["entries"] if e is not None]
    print(f"Found {len(entries)} videos in: {info.get('title', 'Playlist')}")
    print(f"Downloading {len(entries)} videos with {MAX_WORKERS} parallel workers...\n")

    start = time.time()

    # Parallel download
    downloaded = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_single_video, entry, output_dir): entry
            for entry in entries
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                downloaded.append(result)

    # Sort by index
    downloaded.sort(key=lambda x: x["index"])

    elapsed = time.time() - start
    print(f"\nDownloaded {len(downloaded)}/{len(entries)} videos in {elapsed:.1f}s")

    # Save metadata
    meta_path = os.path.join(output_dir, "playlist_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(downloaded, f, indent=2, ensure_ascii=False)
    print(f"Metadata saved → {meta_path}")

    return downloaded


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else input("Paste playlist URL: ").strip()
    results = download_playlist_audio(url, output_dir="./data/audio")
    for r in results:
        print(f"  [{r['index']}] {r['title']} → {r['filepath']}")
