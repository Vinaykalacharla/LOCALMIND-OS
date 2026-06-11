import json
from typing import Any, Dict, List
from .rag import RAGEngine

def detect_contradictions(rag_engine: RAGEngine, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not chunks:
        return {"has_contradiction": False, "analysis": "No documents provided to analyze."}

    # Limit to top chunks to avoid context window explosion
    # In a full implementation, we might chunk this or run it per-topic
    sources = [{"text": c.get("text", ""), "source_file": c.get("source_file", ""), "chunk_id": c.get("chunk_id", "")} for c in chunks[:40]]
    
    question = (
        "Carefully analyze these document excerpts for any factual contradictions or conflicting claims. "
        "A contradiction occurs when two sources state mutually exclusive facts. "
        "If you find contradictions, list them clearly with citations to the conflicting sources. "
        "If you do not find any clear contradictions, reply exactly with: 'No contradictions found.'"
    )
    
    analysis = rag_engine.generate_answer(question, sources, answer_mode="answer")
    
    has_contradiction = "no contradictions found" not in analysis.lower()
    
    return {
        "has_contradiction": has_contradiction,
        "analysis": analysis,
        "scanned_chunks": len(sources)
    }
