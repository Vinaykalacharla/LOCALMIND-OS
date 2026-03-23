from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Dict, List


def _has_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def detect_pdf_backend() -> str:
    if _has_module("fitz"):
        return "pymupdf"
    if _has_module("PyPDF2"):
        return "pypdf2"
    return "none"


def build_feature_status(
    models_dir: Path,
    *,
    embedding_mode: str,
    vector_backend: str,
    graph_mode: str,
    llm_mode: str,
) -> List[Dict[str, str]]:
    gguf_files = sorted(p.name for p in models_dir.glob("*.gguf"))
    pdf_backend = detect_pdf_backend()

    def status_row(feature_id: str, label: str, status: str, detail: str) -> Dict[str, str]:
        return {"id": feature_id, "label": label, "status": status, "detail": detail}

    rows = [
        status_row(
            "embeddings",
            "Embeddings",
            "active" if embedding_mode == "sentence-transformers" else "fallback",
            "SentenceTransformers active." if embedding_mode == "sentence-transformers" else "Install sentence-transformers for semantic embeddings.",
        ),
        status_row(
            "vector_index",
            "Vector Index",
            "active" if vector_backend == "faiss" else "fallback",
            "FAISS active." if vector_backend == "faiss" else "Install faiss-cpu for faster vector search.",
        ),
        status_row(
            "graph",
            "Graph Extraction",
            "active" if graph_mode == "spacy" else "fallback",
            (
                "spaCy entity extraction active."
                if graph_mode == "spacy"
                else "spaCy is disabled on Python 3.14; use Python 3.12 or 3.13 for richer topic extraction."
                if graph_mode == "python-3.14-fallback"
                else "Install spaCy plus en_core_web_sm for richer topic extraction."
            ),
        ),
        status_row(
            "pdf",
            "PDF Extraction",
            "active" if pdf_backend == "pymupdf" else "fallback",
            "PyMuPDF active." if pdf_backend == "pymupdf" else "Install PyMuPDF for stronger PDF parsing.",
        ),
    ]

    if llm_mode.startswith("openai:"):
        model_name = llm_mode.split(":", 1)[1]
        rows.append(status_row("llm", "Premium LLM", "active", f"OpenAI model active: {model_name}"))
    elif llm_mode == "llama-cpp":
        rows.append(status_row("llm", "Local LLM", "active", "GGUF model loaded with llama-cpp-python."))
    elif gguf_files:
        rows.append(
            status_row(
                "llm",
                "Local LLM",
                "fallback",
                f"Found GGUF model(s): {', '.join(gguf_files[:2])}. Install llama-cpp-python to enable them.",
            )
        )
    else:
        rows.append(status_row("llm", "Local LLM", "missing", "Add a GGUF model under backend/models and install llama-cpp-python."))

    return rows
