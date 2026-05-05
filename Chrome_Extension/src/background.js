/**
 * background.js — Service Worker
 *
 * Handles all communication with the backend API.
 * Content scripts send messages here; this worker makes the fetch() calls.
 * This keeps the API key out of the content script (which users could inspect).
 */

// ─────────────────────────────────────────────────────────────────────────────
// Config (loaded from chrome.storage.sync, set via popup Settings tab)
// ─────────────────────────────────────────────────────────────────────────────

async function getConfig() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(
      { apiUrl: "http://localhost:8000", apiKey: "changeme" },
      resolve
    );
  });
}


// ─────────────────────────────────────────────────────────────────────────────
// API helpers
// ─────────────────────────────────────────────────────────────────────────────

async function apiPost(endpoint, body) {
  const { apiUrl, apiKey } = await getConfig();
  const resp = await fetch(`${apiUrl}${endpoint}`, {
    method:  "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key":    apiKey,
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }

  return resp.json();
}

async function apiGet(endpoint) {
  const { apiUrl, apiKey } = await getConfig();
  const resp = await fetch(`${apiUrl}${endpoint}`, {
    headers: { "x-api-key": apiKey },
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }

  return resp.json();
}


// ─────────────────────────────────────────────────────────────────────────────
// Message handler — content script sends messages, we respond
// ─────────────────────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Must return true to use sendResponse asynchronously
  handleMessage(message).then(sendResponse).catch((err) =>
    sendResponse({ error: err.message })
  );
  return true;
});


async function handleMessage(msg) {
  switch (msg.type) {

    // ── Index a playlist ────────────────────────────────────────────────────
    case "INDEX_PLAYLIST": {
      return apiPost("/index", {
        playlist_url:  msg.playlistUrl,
        playlist_id:   msg.playlistId,
        whisper_model: msg.whisperModel || "base",
        chunk_seconds: 60,
      });
    }

    // ── Poll indexing status ────────────────────────────────────────────────
    case "GET_STATUS": {
      return apiGet(`/status/${msg.playlistId}`);
    }

    // ── Semantic search ─────────────────────────────────────────────────────
    case "SEARCH": {
      return apiPost("/search", {
        query:       msg.query,
        playlist_id: msg.playlistId || null,
        top_k:       msg.topK || 5,
      });
    }

    // ── List all indexed playlists ──────────────────────────────────────────
    case "LIST_PLAYLISTS": {
      return apiGet("/playlists");
    }

    // ── Health check ────────────────────────────────────────────────────────
    case "HEALTH": {
      return apiGet("/health");
    }

    default:
      throw new Error(`Unknown message type: ${msg.type}`);
  }
}
