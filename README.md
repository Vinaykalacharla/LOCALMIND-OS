# LocalMind OS

LocalMind OS is a local-first knowledge workspace built for private document ingestion, semantic search, grounded chat, and knowledge exploration. The project combines a Next.js frontend with a FastAPI backend, FAISS-based vector retrieval, encrypted local storage, and an optional offline GGUF model runtime through `llama-cpp-python`.

## What It Does

- Ingest PDFs, notes, code, and structured text files into a local knowledge base
- Chunk and embed documents for semantic search
- Run grounded RAG chat over local data
- Scope questions to selected files only
- Show trust signals such as evidence quality and confidence status
- Generate different answer formats such as direct answers, study guides, flashcards, and quizzes
- Explore a lightweight knowledge graph and activity insights
- Encrypt persisted local data with a user passphrase

## Current Feature Set

### Retrieval and chat

- Hybrid retrieval using dense vector search plus lexical reranking
- `top_k` retrieval controls for search
- Trust-mode chat that can refuse weakly grounded answers
- Inline citations and evidence panels for retrieved sources
- File-scoped chat for asking from selected documents only

### Study workflows

- Standard grounded answer mode
- Study guide mode
- Flashcards mode
- Quiz mode

### Local-first security

- Passphrase-based vault setup
- Encrypted persisted runtime artifacts
- Local document storage under the backend runtime directory

## Architecture

```text
Next.js frontend
  -> FastAPI backend
  -> document extraction
  -> paragraph-aware chunking
  -> sentence-transformers embeddings
  -> FAISS vector index
  -> hybrid reranking
  -> local GGUF model via llama-cpp-python
  -> grounded answer + evidence metadata
```

## Tech Stack

### Frontend

- Next.js 14
- React 18
- TypeScript
- Tailwind CSS

### Backend

- FastAPI
- Uvicorn
- Pydantic
- NumPy

### Local AI stack

- SentenceTransformers (`all-MiniLM-L6-v2`) for embeddings
- FAISS for vector search
- `llama-cpp-python` for local inference
- GGUF models for offline generation
- PyMuPDF / PyPDF2 for PDF extraction

### Security

- Scrypt for key derivation
- AES-GCM for encrypted local artifacts

## Repository Layout

```text
.
|- backend/
|  |- main.py
|  |- services/
|  |- tests/
|  |- demo_data/
|  |- data/            # runtime-generated, ignored from git
|  `- models/          # local GGUF models, ignored from git
|- frontend/
|  |- src/
|  `- package.json
`- README.md
```

## Getting Started

### 1. Backend setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt -r requirements-ai.txt
```

Run the API:

```powershell
uvicorn main:app --host 127.0.0.1 --port 8000
```

Backend docs:

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2. Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

Frontend:

- [http://localhost:3000](http://localhost:3000)

## Offline Model Setup

The repo intentionally does not commit GGUF model binaries. Place a local model file under `backend/models/`.

Recommended range for an 8 GB RAM CPU-only laptop:

- `1.5B` to `3B` instruct models
- quantization such as `Q4_K_M`

Example tested locally:

- `qwen2.5-1.5b-instruct-q4_k_m.gguf`

Once a supported GGUF file is present and `llama-cpp-python` is installed, the backend can use the fully local `llama-cpp` path.

## Security and Passphrase

On first run, create a passphrase in the UI. That passphrase protects persisted runtime artifacts under `backend/data`.

Important:

- If the passphrase is forgotten, the encrypted runtime data cannot be recovered through the application.
- The safe workflow is to keep original source files outside the app so the vault can be rebuilt if needed.

## Git Notes

This repository ignores:

- Python virtual environments
- `node_modules`
- Next.js build output
- backend runtime data
- local GGUF model binaries
- server log files

That keeps the repo pushable and reproducible while still documenting how to restore the local runtime environment.

## Quality and Testing

Backend tests:

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Frontend production build:

```powershell
cd frontend
npm run build
```

## Roadmap

- Rebuild/reindex controls from the UI
- Contradiction detection across uploaded files
- Persistent collections / workspaces
- Version-aware document diffs
- Stronger local model options for larger machines

## Local Documentation

- Backend details: [backend/README.md](backend/README.md)
- Frontend details: [frontend/README.md](frontend/README.md)
- Model folder notes: [backend/models/README.md](backend/models/README.md)
