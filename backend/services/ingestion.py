from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class ExtractedDocument:
    source_file: str
    page_number: Optional[int]
    text: str
    source_id: Optional[str] = None


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _extract_pdf_with_fitz(path: Path) -> List[ExtractedDocument]:
    import fitz  # type: ignore

    out: List[ExtractedDocument] = []
    source_id = _file_digest(path)
    with fitz.open(path) as doc:
        for idx, page in enumerate(doc):
            text = page.get_text("text") or ""
            out.append(
                ExtractedDocument(
                    source_file=path.name,
                    page_number=idx + 1,
                    text=text,
                    source_id=source_id,
                )
            )
    return out


def _extract_pdf_with_pypdf2(path: Path) -> List[ExtractedDocument]:
    from PyPDF2 import PdfReader  # type: ignore

    out: List[ExtractedDocument] = []
    source_id = _file_digest(path)
    reader = PdfReader(str(path))
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        out.append(
            ExtractedDocument(
                source_file=path.name,
                page_number=idx + 1,
                text=text,
                source_id=source_id,
            )
        )
    return out


def extract_from_path(path: Path) -> List[ExtractedDocument]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            return _extract_pdf_with_fitz(path)
        except Exception:
            return _extract_pdf_with_pypdf2(path)

    if suffix in {".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h", ".go", ".rs", ".json", ".yaml", ".yml"}:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".json":
            try:
                loaded = json.loads(raw)
                raw = json.dumps(loaded, indent=2, ensure_ascii=True)
            except Exception:
                pass
        return [ExtractedDocument(source_file=path.name, page_number=None, text=raw, source_id=_file_digest(path))]

    return []


def extract_many(paths: List[Path]) -> List[ExtractedDocument]:
    all_docs: List[ExtractedDocument] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        docs = extract_from_path(path)
        all_docs.extend([d for d in docs if d.text and d.text.strip()])
    return all_docs
