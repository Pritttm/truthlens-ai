# 🔎 TruthLens AI – Misinformation Detection System

> **LLM + RAG-powered fact-checking for news articles and social media posts.**

![TruthLens AI](https://img.shields.io/badge/TruthLens-AI-0ea5e9?style=for-the-badge&logo=openai)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/React-18-61dafb?style=for-the-badge&logo=react)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-ff6b35?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

---

## 📖 Project Overview

TruthLens AI is a production-ready misinformation detection system. Paste any
news article or social media post, and the system will:

1. **Extract** key factual claims using an LLM
2. **Retrieve** relevant evidence from a trusted knowledge base (ChromaDB + Wikipedia)
3. **Score** each claim via RAG-augmented LLM reasoning
4. **Return** a credibility report with scores, explanations, and cited sources

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     User Interface                       │
│              React + TailwindCSS (Vercel)                │
└──────────────────────────┬──────────────────────────────┘
                           │ POST /analyze
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Backend                        │
│                  (Render.com / Docker)                    │
│                                                          │
│  ┌─────────────────┐     ┌──────────────────────────┐   │
│  │ ClaimExtractor  │────▶│     RagPipeline           │   │
│  │  (LLM / regex)  │     │  ┌────────────────────┐  │   │
│  └─────────────────┘     │  │  ChromaDB          │  │   │
│                           │  │  (Vector Search)   │  │   │
│  ┌─────────────────┐     │  └────────────────────┘  │   │
│  │  FactChecker    │◀────│  ┌────────────────────┐  │   │
│  │  (LLM Scoring)  │     │  │  Wikipedia API     │  │   │
│  └────────┬────────┘     │  └────────────────────┘  │   │
│           │               └──────────────────────────┘   │
│           ▼                                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │  AnalyzeResponse                                 │    │
│  │  { credibility_score, misinformation_prob,       │    │
│  │    explanation, claims[], sources[] }            │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## 🗂️ Project Structure

```
truthlens-ai/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app + /analyze endpoint
│   │   ├── claim_extractor.py # LLM claim extraction
│   │   ├── embeddings.py      # sentence-transformers wrapper
│   │   ├── rag_pipeline.py    # ChromaDB + Wikipedia retrieval
│   │   ├── fact_checker.py    # LLM scoring per claim
│   │   └── scraper.py         # Optional URL article scraper
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Full React UI (single-file)
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── .env.example
├── render.yaml                # Render.com deployment config
├── docker-compose.yml
└── README.md
```

---

## ⚙️ Tech Stack

| Layer       | Technology                                      |
|-------------|------------------------------------------------|
| Backend     | Python 3.11+, FastAPI, Uvicorn                  |
| AI / LLM    | OpenAI GPT-4o-mini (or any OpenAI model)        |
| Embeddings  | sentence-transformers `all-MiniLM-L6-v2`        |
| Vector DB   | ChromaDB (persistent, local or cloud)           |
| RAG         | LangChain orchestration + Wikipedia REST API    |
| Frontend    | React 18, Vite, TailwindCSS                     |
| Deployment  | Render.com (backend), Vercel (frontend)         |

---

## 🚀 Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- An OpenAI API key (`sk-...`)

### 1. Clone the repo

```bash
git clone https://github.com/your-username/truthlens-ai.git
cd truthlens-ai
```

### 2. Backend setup

```bash
cd backend

# Create & activate virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Start the backend
uvicorn app.main:app --reload --port 8000
```

The API will be live at **http://localhost:8000**

Swagger docs: **http://localhost:8000/docs**

### 3. Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# (Optional) Configure API URL for production
cp .env.example .env
# Leave VITE_API_URL blank for local dev (uses Vite proxy)

# Start dev server
npm run dev
```

Open **http://localhost:5173**

---

## 📡 API Reference

### `POST /analyze`

Analyzes text for misinformation using the RAG pipeline.

**Request body:**
```json
{
  "text": "The article text to analyze…",
  "url": "https://optional-url-to-scrape.com"
}
```

**Response:**
```json
{
  "credibility_score": 62,
  "misinformation_probability": "Moderate",
  "explanation": "The content has mixed credibility…",
  "claims": [
    {
      "claim": "Scientists discovered a new vaccine.",
      "credibility_score": 78,
      "assessment": "Likely True"
    }
  ],
  "sources": [
    "https://en.wikipedia.org/wiki/Vaccine",
    "WHO Vaccine Safety Fact Sheet, 2022"
  ],
  "processing_time_ms": 2340
}
```

**Assessment values:**
| Value | Meaning |
|-------|---------|
| `Verified` | Directly confirmed by trusted sources |
| `Likely True` | Supported but not 100% confirmed |
| `Unverifiable` | No relevant evidence found |
| `Misleading` | Partially true but omits key context |
| `Likely False` | Contradicts credible sources |
| `False` | Directly refuted by trusted sources |

**Credibility score guide:**
| Score | Probability Label | Interpretation |
|-------|-------------------|----------------|
| 80–100 | Low | Credible content |
| 55–79 | Moderate | Mixed / needs review |
| 30–54 | High | Likely misleading |
| 0–29 | Very High | Probable misinformation |

### `GET /health`

```json
{ "status": "ok", "service": "TruthLens AI" }
```

---

## ☁️ Deployment

### Backend → Render.com

1. Push your code to GitHub
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repo
4. Set:
   - **Root directory:** `backend`
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variable: `OPENAI_API_KEY` = your key
6. Click **Deploy**

Or use the included `render.yaml` for one-click deployment:

```bash
# From repo root
render deploy
```

### Frontend → Vercel

```bash
cd frontend
npm run build              # build static files

# Option A: Vercel CLI
npx vercel --prod

# Option B: Vercel dashboard
# Import GitHub repo → set Root Directory to "frontend"
```

Set environment variable in Vercel:
```
VITE_API_URL = https://your-render-backend.onrender.com
```

### Docker (optional)

```bash
# From repo root
docker-compose up --build
```

---

## 🔑 Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | — | OpenAI API key |
| `LLM_MODEL` | No | `gpt-4o-mini` | LLM model name |
| `EMBEDDING_MODEL` | No | `all-MiniLM-L6-v2` | HuggingFace embedding model |
| `CHROMA_PERSIST_DIR` | No | `./chroma_db` | ChromaDB storage path |
| `CORS_ORIGINS` | No | `*` | Allowed frontend origins |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | In prod | Backend URL (leave blank for local dev) |

---

## 🧪 Running Tests

```bash
cd backend
pytest tests/ -v
```

---

## 🛡️ Limitations & Disclaimer

- TruthLens AI is an **AI-assisted** tool, not a replacement for professional fact-checkers.
- Accuracy depends on the quality of retrieved sources.
- The heuristic fallback (when no API key is set) is significantly less accurate than the LLM path.
- Wikipedia coverage varies by topic.

---

## 📜 License

MIT © TruthLens AI Contributors
