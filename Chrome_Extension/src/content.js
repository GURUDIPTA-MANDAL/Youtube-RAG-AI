/**
 * content.js — runs inside YouTube playlist and watch pages
 *
 * Responsibilities:
 *   1. Detect which playlist the user is on
 *   2. Inject the search sidebar into the YouTube page
 *   3. Handle "jump to timestamp" clicks by seeking the YouTube player
 *   4. Auto-trigger indexing when a new playlist is detected
 */

(function () {
  "use strict";

  // Don't inject twice
  if (document.getElementById("pls-sidebar")) return;

  // ─────────────────────────────────────────────────────────────────────────
  // Detect playlist context
  // ─────────────────────────────────────────────────────────────────────────

  function getPlaylistId() {
    const params = new URLSearchParams(window.location.search);
    return params.get("list") || null;
  }

  function getPlaylistUrl() {
    const pid = getPlaylistId();
    return pid ? `https://www.youtube.com/playlist?list=${pid}` : null;
  }

  function isPlaylistPage() {
    return window.location.pathname === "/playlist" ||
           (window.location.pathname === "/watch" && getPlaylistId());
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Jump to timestamp in the YouTube player
  // ─────────────────────────────────────────────────────────────────────────

  function jumpToVideo(videoId, startSeconds) {
    const currentVideoId = new URLSearchParams(window.location.search).get("v");

    if (currentVideoId === videoId) {
      // Same video — just seek
      const player = document.querySelector("video");
      if (player) {
        player.currentTime = startSeconds;
        player.play();
        return;
      }
    }

    // Different video — navigate with timestamp
    window.location.href =
      `https://www.youtube.com/watch?v=${videoId}&list=${getPlaylistId()}&t=${Math.floor(startSeconds)}s`;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Format seconds → MM:SS
  // ─────────────────────────────────────────────────────────────────────────

  function fmtTime(s) {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Messaging helpers
  // ─────────────────────────────────────────────────────────────────────────

  function sendMsg(msg) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(msg, (resp) => {
        if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
        if (resp && resp.error) return reject(new Error(resp.error));
        resolve(resp);
      });
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Build the sidebar HTML
  // ─────────────────────────────────────────────────────────────────────────

  function createSidebar() {
    const sidebar = document.createElement("div");
    sidebar.id = "pls-sidebar";
    sidebar.innerHTML = `
      <div id="pls-header">
        <span id="pls-logo">🔍</span>
        <span id="pls-title">PlaylistSearch</span>
        <button id="pls-close" title="Close">✕</button>
      </div>

      <div id="pls-status-bar"></div>

      <div id="pls-search-area">
        <input id="pls-input"
               type="text"
               placeholder="e.g. where is recursion explained?"
               autocomplete="off" />
        <button id="pls-search-btn">Search</button>
      </div>

      <div id="pls-index-area">
        <button id="pls-index-btn">⬇ Index this playlist</button>
        <div id="pls-index-progress" style="display:none">
          <div id="pls-progress-bar"><div id="pls-progress-fill"></div></div>
          <span id="pls-progress-label">Starting...</span>
        </div>
      </div>

      <div id="pls-results"></div>
    `;
    return sidebar;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Toggle button (floating pill to open sidebar)
  // ─────────────────────────────────────────────────────────────────────────

  function createToggle() {
    const btn = document.createElement("button");
    btn.id = "pls-toggle";
    btn.textContent = "🔍 Search";
    btn.title = "Open PlaylistSearch";
    return btn;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render search results
  // ─────────────────────────────────────────────────────────────────────────

  function renderResults(data) {
    const container = document.getElementById("pls-results");
    container.innerHTML = "";

    // LLM answer block
    if (data.answer) {
      const answerEl = document.createElement("div");
      answerEl.className = "pls-answer";
      answerEl.innerHTML = `<div class="pls-answer-label">AI Answer</div>
                            <div class="pls-answer-text">${escHtml(data.answer)}</div>`;
      container.appendChild(answerEl);
    }

    // Individual result cards
    if (!data.results || data.results.length === 0) {
      container.innerHTML += `<div class="pls-empty">No results found. Try different keywords.</div>`;
      return;
    }

    data.results.forEach((r, i) => {
      const card = document.createElement("div");
      card.className = "pls-card";
      card.innerHTML = `
        <div class="pls-card-header">
          <span class="pls-video-badge">Video ${r.video_index}</span>
          <span class="pls-timestamp">⏱ ${fmtTime(r.start)}</span>
          <span class="pls-score">${Math.round(r.score * 100)}% match</span>
        </div>
        <div class="pls-card-title">${escHtml(r.title)}</div>
        <div class="pls-card-text">${escHtml(r.text)}</div>
        <button class="pls-jump-btn"
                data-video-id="${r.video_id}"
                data-start="${r.start}">
          ▶ Jump to ${fmtTime(r.start)}
        </button>
      `;
      container.appendChild(card);
    });

    // Attach jump handlers
    container.querySelectorAll(".pls-jump-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        jumpToVideo(btn.dataset.videoId, parseFloat(btn.dataset.start));
      });
    });
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Status bar helpers
  // ─────────────────────────────────────────────────────────────────────────

  function setStatus(msg, type = "info") {
    const bar = document.getElementById("pls-status-bar");
    if (!bar) return;
    bar.textContent = msg;
    bar.className = `pls-status-${type}`;
    bar.style.display = msg ? "block" : "none";
  }

  function setProgress(pct, label) {
    const wrap  = document.getElementById("pls-index-progress");
    const fill  = document.getElementById("pls-progress-fill");
    const lbl   = document.getElementById("pls-progress-label");
    if (!wrap) return;
    wrap.style.display = "block";
    fill.style.width   = `${pct}%`;
    lbl.textContent    = label;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Indexing flow
  // ─────────────────────────────────────────────────────────────────────────

  async function startIndexing() {
    const pid = getPlaylistId();
    if (!pid) {
      setStatus("No playlist detected on this page.", "error");
      return;
    }

    document.getElementById("pls-index-btn").disabled = true;
    setStatus("Sending indexing request...", "info");

    try {
      await sendMsg({
        type:        "INDEX_PLAYLIST",
        playlistUrl: getPlaylistUrl(),
        playlistId:  pid,
      });

      setStatus("Indexing started — this can take several minutes.", "info");
      pollStatus(pid);
    } catch (err) {
      setStatus(`Error: ${err.message}`, "error");
      document.getElementById("pls-index-btn").disabled = false;
    }
  }

  function pollStatus(pid) {
    const interval = setInterval(async () => {
      try {
        const s = await sendMsg({ type: "GET_STATUS", playlistId: pid });

        const labels = {
          queued:       "Queued…",
          downloading:  "Downloading audio…",
          transcribing: "Transcribing with Whisper…",
          embedding:    "Building embeddings…",
          done:         "✅ Indexed!",
          error:        `Error: ${s.error}`,
        };

        setProgress(s.progress || 0, labels[s.status] || s.status);
        setStatus(labels[s.status] || s.status, s.status === "error" ? "error" : "info");

        if (s.status === "done" || s.status === "error") {
          clearInterval(interval);
          document.getElementById("pls-index-btn").disabled = false;
          if (s.status === "done") {
            setStatus(`✅ Ready! ${s.chunk_count} transcript chunks indexed.`, "success");
          }
        }
      } catch (e) {
        // ignore transient errors during polling
      }
    }, 3000);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Search flow
  // ─────────────────────────────────────────────────────────────────────────

  async function doSearch() {
    const input = document.getElementById("pls-input");
    const query = input.value.trim();
    if (!query) return;

    const resultsEl = document.getElementById("pls-results");
    resultsEl.innerHTML = `<div class="pls-loading">🔎 Searching…</div>`;
    setStatus("", "info");

    try {
      const data = await sendMsg({
        type:       "SEARCH",
        query,
        playlistId: getPlaylistId(),
        topK:       5,
      });
      renderResults(data);
    } catch (err) {
      resultsEl.innerHTML = `<div class="pls-error">Error: ${escHtml(err.message)}</div>`;
      setStatus(err.message, "error");
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Mount everything
  // ─────────────────────────────────────────────────────────────────────────

  function mount() {
    if (!isPlaylistPage()) return;

    const sidebar = createSidebar();
    const toggle  = createToggle();
    document.body.appendChild(sidebar);
    document.body.appendChild(toggle);

    // Wire up events
    document.getElementById("pls-close").addEventListener("click", () => {
      sidebar.classList.remove("pls-open");
    });

    toggle.addEventListener("click", () => {
      sidebar.classList.toggle("pls-open");
    });

    document.getElementById("pls-index-btn").addEventListener("click", startIndexing);

    document.getElementById("pls-search-btn").addEventListener("click", doSearch);

    document.getElementById("pls-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") doSearch();
    });

    // Auto-check if this playlist is already indexed
    const pid = getPlaylistId();
    if (pid) {
      sendMsg({ type: "GET_STATUS", playlistId: pid })
        .then((s) => {
          if (s.status === "done") {
            setStatus("✅ Playlist indexed — ready to search!", "success");
          }
        })
        .catch(() => {
          setStatus("Playlist not yet indexed. Click 'Index this playlist' to start.", "info");
        });
    }
  }

  // Run on page load (and re-run on YouTube's SPA navigation)
  mount();

  let lastUrl = location.href;
  new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      if (!document.getElementById("pls-sidebar")) mount();
    }
  }).observe(document, { subtree: true, childList: true });
})();
