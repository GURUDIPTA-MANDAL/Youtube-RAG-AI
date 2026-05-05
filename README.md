# Youtube-RAG-AI

 #OVERALL ARCHITECTURE
<img width="702" height="574" alt="image" src="https://github.com/user-attachments/assets/c4281396-d493-49a4-9d6f-8baab293a22d" />

Here's how it works:
→ You visit any YouTube playlist
→ My extension indexes all videos automatically
→ You ask: "where is recursion explained?"
→ AI finds the exact moment across ALL videos
→ One click jumps you directly there ⏱

🛠 Tech Stack I built this with:
- Python + FastAPI (backend REST API)
- faster-whisper (local speech-to-text)
- Ollama + nomic-embed-text (local embeddings)
- RAG (Retrieval Augmented Generation)
- LLaMA 3.2 (local LLM — runs 100% offline!)
- Chrome Extension (Manifest V3)
- Cosine Similarity search

💡 The best part? Everything runs LOCALLY on your 
machine. No OpenAI API costs. No data sent to cloud.
Complete privacy.


#SCREENSHOT
<img width="1417" height="956" alt="image" src="https://github.com/user-attachments/assets/04d6585e-d43a-425f-9126-0962dc0e20a8" />

#INSTALLATION STEP


## PART 1 — One-time Setup

### 1. Install FFmpeg (required for audio conversion)
```bash
# In Anaconda Prompt (run as Administrator):
conda install -c conda-forge ffmpeg -y
```
Verify: `ffmpeg -version`

---

### 2. Install Ollama
1. Go to https://ollama.ai and download for Windows
2. Install and run it
3. Pull the faster models:
```bash
ollama pull nomic-embed-text
ollama pull llama3.2:3b
```
Verify: `ollama list` — should show both models

---

### 3. Install Python packages
```bash
cd "R:\My Projects\Youtube-RAG-AI\Backend"
conda activate booksenv
pip install -r requirements.txt
```

---

### 4. Create .env file
```bash
copy .env.example .env
```
Open `.env` and set:
```
API_KEY=mysecretkey123
OLLAMA_BASE_URL=http://localhost:11434
EMBED_MODEL=nomic-embed-text
LLM_MODEL=llama3.2:3b
WHISPER_MODEL=base
DATA_DIR=./data
MAX_DOWNLOAD_WORKERS=3
```

---

### 5. Generate Chrome extension icons
```bash
cd "R:\My Projects\Youtube-RAG-AI"
pip install pillow
python generate_icons.py
```
This creates `icon16.png`, `icon48.png`, `icon128.png` in Chrome_Extension/Icons/

---

## PART 2 — Every Time You Use It

### Terminal 1 — Start Ollama
```bash
ollama serve
```
Keep this running.

### Terminal 2 — Start Backend API
```bash
cd "R:\My Projects\Youtube-RAG-AI\Backend"
conda activate booksenv
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```
Keep this running.

Open http://localhost:8000/docs to verify ✅

---

## PART 3 — Load Chrome Extension (once)

1. Open Chrome → go to `chrome://extensions`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select `R:\My Projects\Youtube-RAG-AI\Chrome_Extension`
5. Extension icon appears in toolbar ✅

Configure it:
1. Click extension icon → Settings tab
2. Backend URL: `http://localhost:8000`
3. API Key: `mysecretkey123`
4. Click Save → Status should show 🟢 Connected

---

## PART 4 — Use It

1. Go to any YouTube playlist
2. Click 🔍 Search pill on the right
3. Click ⬇ Index this playlist
4. Wait for completion (much faster now!)
5. Ask questions → click ▶ Jump to timestamp

---




