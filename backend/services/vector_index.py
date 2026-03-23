from __future__ import annotations

import io
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np


class VectorIndex:
    def __init__(self, index_path: Optional[Path] = None):
        self.index_path = index_path
        self._faiss = None
        self._use_faiss = False
        self._index = None
        self._matrix = np.zeros((0, 1), dtype=np.float32)
        self._dim = 0
        self._load_backend()
        self._load_existing()

    @property
    def backend_name(self) -> str:
        return "faiss" if self._use_faiss else "numpy-fallback"

    @property
    def size(self) -> int:
        if self._use_faiss and self._index is not None:
            return int(self._index.ntotal)
        return int(self._matrix.shape[0])

    def _load_backend(self) -> None:
        try:
            import faiss  # type: ignore

            self._faiss = faiss
            self._use_faiss = True
        except Exception:
            self._faiss = None
            self._use_faiss = False

    def _load_existing(self) -> None:
        if self.index_path is None or not self.index_path.exists():
            return
        self.load_bytes(self.index_path.read_bytes())

    def _load_numpy_bytes(self, payload: bytes) -> None:
        try:
            with io.BytesIO(payload) as f:
                matrix = np.load(f, allow_pickle=False)
            matrix = np.asarray(matrix, dtype=np.float32)
            if matrix.ndim == 1:
                matrix = matrix.reshape(1, -1)
            self._matrix = matrix
            self._dim = matrix.shape[1] if matrix.size else 0
        except Exception:
            self._matrix = np.zeros((0, 1), dtype=np.float32)
            self._dim = 0

    def load_bytes(self, payload: bytes) -> None:
        self._index = None
        self._matrix = np.zeros((0, 1), dtype=np.float32)
        self._dim = 0
        if not payload:
            return

        if self._use_faiss and self._faiss is not None:
            try:
                index = self._faiss.deserialize_index(np.frombuffer(payload, dtype=np.uint8))
                self._index = index
                self._dim = int(index.d)
                return
            except Exception:
                self._index = None

        self._load_numpy_bytes(payload)

    def dump_bytes(self) -> bytes | None:
        if self.size == 0:
            return None
        if self._use_faiss and self._faiss is not None and self._index is not None:
            return bytes(self._faiss.serialize_index(self._index))
        if self._matrix.size == 0:
            return None
        with io.BytesIO() as f:
            np.save(f, self._matrix, allow_pickle=False)
            return f.getvalue()

    def rebuild(self, vectors: np.ndarray) -> None:
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.size == 0:
            self._dim = 0
            self._index = None
            self._matrix = np.zeros((0, 1), dtype=np.float32)
            if self.index_path is not None and self.index_path.exists():
                self.index_path.unlink(missing_ok=True)
            return

        if vectors.ndim != 2:
            raise ValueError("vectors must be a 2D matrix")
        self._dim = vectors.shape[1]

        if self._use_faiss and self._faiss is not None:
            index = self._faiss.IndexFlatIP(self._dim)
            index.add(vectors)
            self._index = index
            self._matrix = np.zeros((0, 1), dtype=np.float32)
            return

        self._matrix = vectors

    def search(self, query_vector: np.ndarray, top_k: int) -> List[Tuple[int, float]]:
        if top_k <= 0:
            top_k = 5
        if self.size == 0:
            return []

        q = np.asarray(query_vector, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)

        if self._use_faiss and self._index is not None:
            distances, indices = self._index.search(q, min(top_k, self.size))
            out: List[Tuple[int, float]] = []
            for idx, score in zip(indices[0], distances[0]):
                if idx < 0:
                    continue
                out.append((int(idx), float(score)))
            return out

        if self._matrix.size == 0:
            return []
        scores = (self._matrix @ q[0].reshape(-1, 1)).reshape(-1)
        order = np.argsort(-scores)[: min(top_k, scores.shape[0])]
        return [(int(i), float(scores[i])) for i in order]
