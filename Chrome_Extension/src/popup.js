/**
 * popup.js — runs inside the extension popup window
 * Handles: tab switching, settings save/load, status display
 */

// ── Tab switching ─────────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab, .panel").forEach((el) =>
      el.classList.remove("active")
    );
    tab.classList.add("active");
    document.getElementById(`panel-${tab.dataset.panel}`).classList.add("active");
  });
});


// ── Settings: load saved values ───────────────────────────────────────────────
chrome.storage.sync.get(
  { apiUrl: "http://localhost:8000", apiKey: "changeme", whisperModel: "base" },
  (cfg) => {
    document.getElementById("api-url").value       = cfg.apiUrl;
    document.getElementById("api-key").value       = cfg.apiKey;
    document.getElementById("whisper-model").value = cfg.whisperModel;
  }
);


// ── Settings: save ────────────────────────────────────────────────────────────
document.getElementById("save-btn").addEventListener("click", () => {
  const cfg = {
    apiUrl:       document.getElementById("api-url").value.trim().replace(/\/$/, ""),
    apiKey:       document.getElementById("api-key").value.trim(),
    whisperModel: document.getElementById("whisper-model").value,
  };

  chrome.storage.sync.set(cfg, () => {
    const msg = document.getElementById("save-msg");
    msg.textContent = "✅ Saved!";
    setTimeout(() => (msg.textContent = ""), 2000);

    // Re-check API health after saving new URL
    checkApiHealth(cfg.apiUrl, cfg.apiKey);
  });
});


// ── Status: check API health ──────────────────────────────────────────────────
async function checkApiHealth(apiUrl, apiKey) {
  const dot  = document.getElementById("api-dot");
  const text = document.getElementById("api-status-text");

  try {
    const resp = await fetch(`${apiUrl}/health`, {
      headers: { "x-api-key": apiKey },
    });
    if (resp.ok) {
      dot.className  = "status-dot green";
      text.textContent = "Connected";
    } else {
      dot.className  = "status-dot red";
      text.textContent = `Error ${resp.status}`;
    }
  } catch {
    dot.className  = "status-dot red";
    text.textContent = "Unreachable";
  }
}


// ── Status: detect current page type ─────────────────────────────────────────
chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
  const el = document.getElementById("page-type");
  if (!tab?.url) return;

  const url = new URL(tab.url);
  if (url.pathname === "/playlist") {
    const pid = url.searchParams.get("list");
    el.textContent = `📋 Playlist: ${pid || "?"}`;
    el.style.color = "#2e7d32";
  } else if (url.pathname === "/watch" && url.searchParams.get("list")) {
    el.textContent = `▶ Watch page (with playlist)`;
    el.style.color = "#1565c0";
  } else if (url.hostname === "www.youtube.com") {
    el.textContent = "YouTube — no playlist detected";
    el.style.color = "#888";
  } else {
    el.textContent = "Not on YouTube";
    el.style.color = "#888";
  }
});


// ── Status: load indexed playlists ────────────────────────────────────────────
async function loadPlaylists(apiUrl, apiKey) {
  const listEl = document.getElementById("playlist-list");
  try {
    const resp = await fetch(`${apiUrl}/playlists`, {
      headers: { "x-api-key": apiKey },
    });
    const data = await resp.json();

    if (!data.playlists || data.playlists.length === 0) {
      listEl.innerHTML = `<div class="empty-msg">No playlists indexed yet.</div>`;
      return;
    }

    listEl.innerHTML = data.playlists
      .map(
        (p) => `
      <div class="playlist-item">
        <div class="playlist-id">${p.playlist_id}</div>
        <div class="playlist-meta">${p.video_count} videos · ${p.chunk_count} chunks</div>
      </div>`
      )
      .join("");
  } catch {
    listEl.innerHTML = `<div class="empty-msg" style="color:#c62828">Could not load playlists.</div>`;
  }
}


// ── Init ──────────────────────────────────────────────────────────────────────
chrome.storage.sync.get(
  { apiUrl: "http://localhost:8000", apiKey: "changeme" },
  ({ apiUrl, apiKey }) => {
    checkApiHealth(apiUrl, apiKey);
    loadPlaylists(apiUrl, apiKey);
  }
);