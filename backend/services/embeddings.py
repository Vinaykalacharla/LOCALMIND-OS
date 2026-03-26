from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")
HASHED_TFIDF_DIM = 2048
HASHED_TFIDF_VERSION = "stable-blake2b-v1"
DEFAULT_EMBEDDING_CANDIDATES = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "all-MiniLM-L6-v2",
]


def _tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix.astype(np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-12
    return (matrix / norms).astype(np.float32)


@dataclass
class EmbeddingResult:
    vectors: np.ndarray
    model_name: str
    mode: str


class HashedTfidfEncoder:
    def __init__(self, dim: int = HASHED_TFIDF_DIM) -> None:
        self.dim = dim
        self.idf = np.ones((dim,), dtype=np.float32)
        self.fitted = False

    def _index(self, token: str) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, byteorder="little", signed=False) % self.dim

    def fit(self, texts: List[str]) -> None:
        n_docs = max(1, len(texts))
        df = np.zeros((self.dim,), dtype=np.float32)
        for text in texts:
            seen = set()
            for token in _tokenize(text):
                seen.add(self._index(token))
            for idx in seen:
                df[idx] += 1.0
        self.idf = (np.log((n_docs + 1.0) / (df + 1.0)) + 1.0).astype(np.float32)
        self.fitted = True

    def transform(self, texts: List[str]) -> np.ndarray:
        rows = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            counts: Dict[int, int] = {}
            for token in _tokenize(text):
                idx = self._index(token)
                counts[idx] = counts.get(idx, 0) + 1
            total = max(1, sum(counts.values()))
            for idx, cnt in counts.items():
                tf = cnt / total
                rows[i, idx] = tf * float(self.idf[idx])
        return _l2_normalize(rows)


class EmbeddingService:
    def __init__(self, models_dir: Path | None = None, preferred_model: str | None = None) -> None:
        self.models_dir = models_dir or (Path(__file__).resolve().parents[1] / "models")
        self.preferred_model = (preferred_model or "").strip()
        self.mode = "hashed-tfidf"
        self.model_name = f"hashed-tfidf-{HASHED_TFIDF_DIM}"
        self.last_error = ""
        self._st_model = None
        self._fallback = HashedTfidfEncoder(dim=HASHED_TFIDF_DIM)
        self._initialize_primary()

    def _resolve_candidate(self, candidate: str) -> str:
        resolved = Path(candidate)
        if not resolved.is_absolute():
            local_path = self.models_dir / candidate
            if local_path.exists():
                resolved = local_path
        return str(resolved)

    def _embedding_candidates(self) -> List[str]:
        seen: set[str] = set()
        candidates: List[str] = []

        def add(candidate: str) -> None:
            normalized = candidate.strip()
            if not normalized:
                return
            key = normalized.lower()
            if key in seen:
                return
            seen.add(key)
            candidates.append(normalized)

        preferred = self.preferred_model.strip()
        if preferred and preferred.lower() not in {"auto", "hashed-tfidf", "fallback"}:
            add(self._resolve_candidate(preferred))
            return candidates

        configured = os.getenv("LOCALMIND_EMBEDDING_MODEL", "").strip()
        if configured:
            add(self._resolve_candidate(configured))

        embedding_dir = self.models_dir / "embeddings"
        if embedding_dir.exists():
            for child in sorted(embedding_dir.iterdir()):
                if child.is_dir():
                    add(str(child))

        for candidate in DEFAULT_EMBEDDING_CANDIDATES:
            add(candidate)

        return candidates

    def _load_sentence_transformer(self, sentence_transformer_cls: Any, candidate: str) -> Any | None:
        try:
            return sentence_transformer_cls(candidate, local_files_only=True)
        except TypeError:
            if Path(candidate).exists():
                try:
                    return sentence_transformer_cls(candidate)
                except Exception as exc:
                    self.last_error = str(exc)
                    return None
            return None
        except Exception as exc:
            self.last_error = str(exc)
            return None

    def _initialize_primary(self) -> None:
        self.last_error = ""
        self._st_model = None
        preferred = self.preferred_model.strip().lower()
        if preferred in {"hashed-tfidf", "fallback"}:
            self.mode = "hashed-tfidf"
            self.model_name = f"hashed-tfidf-{self._fallback.dim}"
            return

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as exc:
            self.mode = "hashed-tfidf"
            self.model_name = f"hashed-tfidf-{self._fallback.dim}"
            self.last_error = str(exc)
            return

        for candidate in self._embedding_candidates():
            loaded = self._load_sentence_transformer(SentenceTransformer, candidate)
            if loaded is None:
                continue
            self._st_model = loaded
            self.mode = "sentence-transformers"
            self.model_name = Path(candidate).name if Path(candidate).exists() else candidate
            return

        self.mode = "hashed-tfidf"
        self.model_name = f"hashed-tfidf-{self._fallback.dim}"
        if self.preferred_model.strip() and preferred not in {"", "auto", "hashed-tfidf", "fallback"} and not self.last_error:
            self.last_error = f"Failed to load embedding model: {self.preferred_model}"

    def reload(self, preferred_model: str | None = None) -> None:
        if preferred_model is not None:
            self.preferred_model = preferred_model.strip()
        self.mode = "hashed-tfidf"
        self.model_name = f"hashed-tfidf-{self._fallback.dim}"
        self.last_error = ""
        self._st_model = None
        self._initialize_primary()

    def index_signature(self) -> str:
        if self.mode == "sentence-transformers" and self._st_model is not None:
            return f"sentence-transformers:{self.model_name}"
        return f"hashed-tfidf:{self._fallback.dim}:{HASHED_TFIDF_VERSION}"

    def prepare_runtime(self, texts: List[str]) -> None:
        if self.mode == "sentence-transformers" and self._st_model is not None:
            return

        self.mode = "hashed-tfidf"
        self.model_name = f"hashed-tfidf-{self._fallback.dim}"
        if texts:
            self._fallback.fit(texts)
            return
        self._fallback = HashedTfidfEncoder(dim=self._fallback.dim)

    def embed_corpus(self, texts: List[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(vectors=np.zeros((0, 1), dtype=np.float32), model_name=self.model_name, mode=self.mode)

        if self.mode == "sentence-transformers" and self._st_model is not None:
            vectors = self._st_model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            vectors = np.asarray(vectors, dtype=np.float32)
            return EmbeddingResult(vectors=vectors, model_name=self.model_name, mode=self.mode)

        self._fallback.fit(texts)
        matrix = self._fallback.transform(texts)
        self.mode = "hashed-tfidf"
        self.model_name = f"hashed-tfidf-{self._fallback.dim}"
        return EmbeddingResult(vectors=matrix, model_name=self.model_name, mode=self.mode)

    def embed_query(self, query: str) -> np.ndarray:
        if not query.strip():
            return np.zeros((1, self._fallback.dim), dtype=np.float32)

        if self.mode == "sentence-transformers" and self._st_model is not None:
            vec = self._st_model.encode([query], convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
            return np.asarray(vec, dtype=np.float32)

        if not self._fallback.fitted:
            self._fallback.fit([query])
        return self._fallback.transform([query]).astype(np.float32)
