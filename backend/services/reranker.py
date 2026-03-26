from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence


DEFAULT_RERANKER_CANDIDATES: list[str] = []


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


class RerankerService:
    def __init__(self, models_dir: Path, preferred_model: str | None = None):
        self.models_dir = models_dir
        self.preferred_model = (preferred_model or "").strip()
        self.mode = "disabled"
        self.model_name = "lexical-only"
        self.last_error = ""
        self._cross_encoder = None
        self._initialize()

    def _resolve_candidate(self, candidate: str) -> str:
        resolved = Path(candidate)
        if not resolved.is_absolute():
            local_path = self.models_dir / candidate
            if local_path.exists():
                resolved = local_path
        return str(resolved)

    def _candidate_paths(self) -> List[str]:
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
        if preferred and preferred.lower() not in {"auto", "disabled", "lexical-only"}:
            add(self._resolve_candidate(preferred))
            return candidates

        configured = os.getenv("LOCALMIND_RERANKER_MODEL", "").strip()
        if configured:
            add(self._resolve_candidate(configured))

        reranker_dir = self.models_dir / "rerankers"
        if reranker_dir.exists():
            for child in sorted(reranker_dir.iterdir()):
                if child.is_dir():
                    add(str(child))

        for candidate in DEFAULT_RERANKER_CANDIDATES:
            add(candidate)

        return candidates

    def _load_cross_encoder(self, cross_encoder_cls: Any, candidate: str) -> Any | None:
        try:
            return cross_encoder_cls(candidate, local_files_only=True)
        except TypeError:
            if Path(candidate).exists():
                try:
                    return cross_encoder_cls(candidate)
                except Exception as exc:
                    self.last_error = str(exc)
                    return None
            return None
        except Exception as exc:
            self.last_error = str(exc)
            return None

    def _initialize(self) -> None:
        self.last_error = ""
        self._cross_encoder = None
        preferred = self.preferred_model.strip().lower()
        if preferred in {"disabled", "lexical-only"}:
            self.mode = "disabled"
            self.model_name = "lexical-only"
            return

        try:
            from sentence_transformers import CrossEncoder  # type: ignore
        except Exception as exc:
            self.mode = "disabled"
            self.model_name = "lexical-only"
            self.last_error = str(exc)
            return

        for candidate in self._candidate_paths():
            loaded = self._load_cross_encoder(CrossEncoder, candidate)
            if loaded is None:
                continue
            self._cross_encoder = loaded
            self.mode = "cross-encoder"
            self.model_name = Path(candidate).name if Path(candidate).exists() else candidate
            return

        self.mode = "disabled"
        self.model_name = "lexical-only"
        if self.preferred_model.strip() and preferred not in {"", "auto", "disabled", "lexical-only"} and not self.last_error:
            self.last_error = f"Failed to load reranker model: {self.preferred_model}"

    def reload(self, preferred_model: str | None = None) -> None:
        if preferred_model is not None:
            self.preferred_model = preferred_model.strip()
        self.mode = "disabled"
        self.model_name = "lexical-only"
        self.last_error = ""
        self._cross_encoder = None
        self._initialize()

    def rerank(self, query: str, candidates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.mode != "cross-encoder" or self._cross_encoder is None or len(candidates) < 2:
            return [dict(candidate) for candidate in candidates]

        pairs = [(query, str(candidate.get("text", ""))[:2400]) for candidate in candidates]
        try:
            raw_scores = self._cross_encoder.predict(pairs, show_progress_bar=False)
        except TypeError:
            raw_scores = self._cross_encoder.predict(pairs)
        except Exception:
            return [dict(candidate) for candidate in candidates]

        reranked: List[Dict[str, Any]] = []
        for candidate, raw_score in zip(candidates, raw_scores):
            row = dict(candidate)
            normalized_score = round(_sigmoid(float(raw_score)), 4)
            row["reranker_score"] = normalized_score
            reranked.append(row)
        return reranked
