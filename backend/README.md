# LocalMind OS Backend

Offline FastAPI backend for ingestion, vector search, RAG answering, graph generation, and insights.

## Run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open: http://localhost:8000/docs

## Security

The backend now requires a passphrase before normal routes are usable.

1. Start the backend.
2. Open the frontend.
3. On first run, create a passphrase. Existing persisted data under `backend/data` will be encrypted in place.
4. On later runs, unlock the backend with the same passphrase before using ingest, search, chat, or graph routes.

Persisted uploads, chunks, graph data, metadata, vector index data, and query history are stored encrypted at rest after setup.

## Optional Local AI Stack

Install richer offline capabilities with:

```powershell
pip install -r requirements.txt -r requirements-ai.txt
python -m spacy download en_core_web_sm
```

Optional models:
- Place `*.gguf` files in `backend/models` to enable local generation through `llama-cpp-python`.
- If `sentence-transformers` is installed, the backend will switch from hashed TF-IDF to semantic embeddings automatically.
- Set `OPENAI_API_KEY` to enable a hosted premium LLM.
- Optionally set `OPENAI_MODEL` to choose the hosted model. Default: `gpt-5.4`.
- Optionally set `LOCALMIND_LLM_PROVIDER` to `local`, `openai`, or `auto`. Default: `auto`.

The `/stats` response now exposes active vs fallback capabilities so the frontend can show what is enabled.

## Data Artifacts

Persisted under `backend/data`:
- `chunks.jsonl`
- `faiss.index`
- `index_map.json`
- `meta.json`
- `graph.json`
- `query_log.jsonl`

## Notes
- Embeddings: tries `sentence-transformers` first, falls back to TF-IDF.
- Vector backend: tries FAISS first, falls back to NumPy similarity if FAISS is unavailable.
- LLM mode: in `auto`, it prefers local GGUF via `llama-cpp-python`, then OpenAI if configured, then falls back to extractive answer generation.
- For a truly offline setup, leave `OPENAI_API_KEY` unset and optionally set `LOCALMIND_LLM_PROVIDER=local`.
- Graph: tries spaCy NER/chunks first, falls back to keyword graph extraction.
- Python 3.14: spaCy graph extraction is disabled automatically because the current spaCy stack is not fully compatible there. Use Python 3.12 or 3.13 for richer graph extraction.

## Model Guidance

For the current laptop-class setup in this project, keep expectations realistic:

- Around `8 GB` RAM, CPU-only: prefer `1.5B` to `3B` instruct models in `Q4_K_M` or similar quantization.
- `7B` class models are usually possible only with more RAM and will feel slow or unstable alongside the browser and embedding stack on this machine.
- If you want answers materially closer to ChatGPT quality while staying offline, the next meaningful step is a stronger local machine, then a `7B` or `8B` instruct model plus better retrieval.

Current quality work in this backend focuses on:
- paragraph-aware chunking for new ingests
- hybrid retrieval reranking with lexical matching on top of vector search
- broader retrieval for answer generation before the local model writes the response

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
