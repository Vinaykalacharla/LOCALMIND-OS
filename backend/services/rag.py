from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Sequence
from urllib import error, request


QUESTION_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "does",
    "for",
    "from",
    "give",
    "how",
    "i",
    "in",
    "into",
    "is",
    "it",
    "make",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "show",
    "tell",
    "the",
    "to",
    "using",
    "what",
    "with",
}


def _normalize_answer_mode(answer_mode: str) -> str:
    allowed = {"answer", "study_guide", "flashcards", "quiz"}
    cleaned = answer_mode.strip().lower().replace("-", "_")
    return cleaned if cleaned in allowed else "answer"


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def _extract_sentences(text: str) -> List[str]:
    raw = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s.strip() for s in raw if s and s.strip()]


def _question_terms(question: str) -> set[str]:
    return {token for token in _tokenize(question) if token not in QUESTION_STOPWORDS and len(token) > 2}


def _detect_intent(question: str) -> str:
    lowered = question.lower()
    if any(token in lowered for token in ["compare", "difference", "different", "vs", "versus"]):
        return "compare"
    if any(token in lowered for token in ["plan", "schedule", "roadmap", "revise", "revision"]):
        return "plan"
    if any(token in lowered for token in ["list", "points", "steps", "bullets"]):
        return "list"
    if any(token in lowered for token in ["why", "how", "explain", "what is", "what are"]):
        return "explain"
    return "answer"


def _source_label(source: Dict[str, str]) -> str:
    source_file = source.get("source_file", "unknown")
    page_number = source.get("page_number")
    if page_number:
        return f"{source_file} p.{page_number}"
    return source_file


def _sentence_bonus(intent: str, sentence: str, question_terms: set[str]) -> float:
    lowered = sentence.lower()
    bonus = 0.0
    if intent == "compare" and any(token in lowered for token in ["while", "whereas", "however", "than", "both", "different"]):
        bonus += 0.18
    if intent == "plan" and any(token in lowered for token in ["step", "day", "week", "review", "practice", "focus"]):
        bonus += 0.18
    if intent == "explain" and any(token in lowered for token in ["is", "means", "refers", "because", "therefore"]):
        bonus += 0.14
    if question_terms and any(term in lowered for term in question_terms):
        bonus += 0.08
    return bonus


def _scored_sentences(question: str, sources: Sequence[Dict[str, str]]) -> List[Dict[str, str | float]]:
    question_terms = _question_terms(question)
    intent = _detect_intent(question)
    scored: List[Dict[str, str | float]] = []

    for source_index, source in enumerate(sources):
        label = _source_label(source)
        for sentence_index, sentence in enumerate(_extract_sentences(source.get("text", ""))):
            normalized = " ".join(_tokenize(sentence))
            if len(normalized) < 12:
                continue
            sentence_terms = set(_tokenize(sentence))
            overlap = len(question_terms & sentence_terms)
            score = overlap / max(1, len(question_terms) or 1)
            score += min(len(sentence), 220) / 3000.0
            score += _sentence_bonus(intent, sentence, question_terms)
            score += max(0.0, 0.06 - (source_index * 0.01))
            score += max(0.0, 0.03 - (sentence_index * 0.002))
            scored.append(
                {
                    "text": sentence.strip(),
                    "label": label,
                    "normalized": normalized,
                    "source_index": source_index,
                    "score": score,
                }
            )

    scored.sort(key=lambda row: float(row["score"]), reverse=True)
    return scored


def _top_unique_sentences(question: str, sources: Sequence[Dict[str, str]], limit: int = 6) -> List[Dict[str, str | float]]:
    picked: List[Dict[str, str | float]] = []
    seen: set[str] = set()
    for candidate in _scored_sentences(question, sources):
        normalized = str(candidate["normalized"])
        if normalized in seen:
            continue
        seen.add(normalized)
        picked.append(candidate)
        if len(picked) >= limit:
            break
    return picked


def _format_with_citation(sentence: Dict[str, str | float]) -> str:
    return f"{sentence['text']} [{sentence['label']}]"


def _build_local_evidence(question: str, sources: Sequence[Dict[str, str]], limit: int = 8, max_chars: int = 2200) -> str:
    lines: List[str] = []
    used_chars = 0

    for candidate in _top_unique_sentences(question, sources, limit=max(limit * 2, limit)):
        marker = f"S{int(candidate['source_index']) + 1}"
        line = f"[{marker}] {candidate['text']} ({candidate['label']})"
        if used_chars and used_chars + len(line) > max_chars:
            break
        lines.append(line)
        used_chars += len(line) + 1
        if len(lines) >= limit:
            break

    if lines:
        return "\n".join(lines)

    for index, source in enumerate(sources[:3], start=1):
        sentences = _extract_sentences(source.get("text", ""))[:2]
        if not sentences:
            continue
        label = _source_label(source)
        line = f"[S{index}] {' '.join(sentences)[:280]} ({label})"
        if used_chars and used_chars + len(line) > max_chars:
            break
        lines.append(line)
        used_chars += len(line) + 1

    return "\n".join(lines)


def _local_answer_instruction(question: str, answer_mode: str = "answer") -> str:
    answer_mode = _normalize_answer_mode(answer_mode)
    intent = _detect_intent(question)
    if answer_mode == "study_guide":
        return (
            "Write a compact study guide with these sections: Core idea, Key points, and Recall checks. "
            "Use short bullets and keep every factual claim grounded in the evidence."
        )
    if answer_mode == "flashcards":
        return (
            "Create 4 to 6 flashcards. Format each one as 'Q:' on one line and 'A:' on the next line. "
            "Keep answers short and cite factual claims inline like [S1]."
        )
    if answer_mode == "quiz":
        return (
            "Create 4 short-answer quiz questions followed by an 'Answer key:' section. "
            "Keep the questions clear and grounded in the evidence."
        )
    if intent == "compare":
        return (
            "Give a concise comparison. Start with one direct sentence, then add 2 to 4 short bullets "
            "covering the most important similarities or differences."
        )
    if intent == "plan":
        return "Return 3 to 5 numbered steps using only the evidence. Keep each step practical and short."
    if intent == "list":
        return "Return 3 to 6 short bullets. Avoid filler."
    if intent == "explain":
        return "Start with a direct explanation in 2 to 4 sentences. Add up to 3 short bullets only if useful."
    return "Answer directly in 2 to 4 concise sentences. Add bullets only if they improve clarity."


def _clean_generated_answer(text: str) -> str:
    cleaned = text.strip()
    cleaned = cleaned.replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()
    cleaned = re.sub(r"^\s*(assistant|answer)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _has_citation(text: str) -> bool:
    return bool(re.search(r"\[[^\]]+\]", text))


def _grounding_appendix(question: str, sources: Sequence[Dict[str, str]], limit: int = 2) -> str:
    chosen = _top_unique_sentences(question, sources, limit=limit)
    if not chosen:
        return ""
    bullets = "\n".join(f"- {_format_with_citation(item)}" for item in chosen)
    return f"Key evidence:\n{bullets}"


def _flashcard_prompt(sentence: str, fallback_index: int) -> str:
    lowered = sentence.lower()
    for separator in [" is ", " are ", " refers to ", " means ", " because "]:
        if separator in lowered:
            subject = sentence[: lowered.index(separator)].strip(" -:;,.")
            if len(subject) >= 4:
                return f"What should you remember about {subject}?"
    return f"What is one key point to remember from card {fallback_index}?"


def extractive_answer(question: str, sources: Sequence[Dict[str, str]], answer_mode: str = "answer") -> str:
    answer_mode = _normalize_answer_mode(answer_mode)
    chosen = _top_unique_sentences(question, sources)
    if not chosen:
        return "Not found in your data."

    if answer_mode == "study_guide":
        core_idea = _format_with_citation(chosen[0])
        key_points = "\n".join(f"- {_format_with_citation(item)}" for item in chosen[:4])
        recall_checks = "\n".join(f"- What does your data say about {term}?" for term in sorted(_question_terms(question))[:3])
        if not recall_checks:
            recall_checks = "- What is the main idea?\n- Which evidence supports it?"
        return f"Core idea:\n{core_idea}\n\nKey points:\n{key_points}\n\nRecall checks:\n{recall_checks}"

    if answer_mode == "flashcards":
        cards = []
        for index, item in enumerate(chosen[:4], start=1):
            prompt = _flashcard_prompt(str(item["text"]), index)
            cards.append(f"Q: {prompt}\nA: {_format_with_citation(item)}")
        return "\n\n".join(cards)

    if answer_mode == "quiz":
        questions = []
        answers = []
        for index, item in enumerate(chosen[:4], start=1):
            questions.append(f"{index}. What does your data say about item {index}?")
            answers.append(f"{index}. {_format_with_citation(item)}")
        return f"Quiz:\n" + "\n".join(questions) + "\n\nAnswer key:\n" + "\n".join(answers)

    intent = _detect_intent(question)
    first = _format_with_citation(chosen[0])
    rest = chosen[1:]

    if intent == "compare":
        lines = "\n".join(f"- {_format_with_citation(item)}" for item in chosen[:5])
        return f"Comparison based on your data:\n{lines}"

    if intent == "plan":
        steps = "\n".join(f"{idx + 1}. {_format_with_citation(item)}" for idx, item in enumerate(chosen[:5]))
        return f"Suggested plan from your data:\n{steps}"

    if intent == "list":
        lines = "\n".join(f"- {_format_with_citation(item)}" for item in chosen[:6])
        return f"Relevant points from your data:\n{lines}"

    if intent == "explain":
        bullets = "\n".join(f"- {_format_with_citation(item)}" for item in rest[:4])
        if bullets:
            return f"{first}\n\nSupporting points:\n{bullets}"
        return first

    bullets = "\n".join(f"- {_format_with_citation(item)}" for item in rest[:4])
    if bullets:
        return f"{first}\n\nAdditional context:\n{bullets}"
    return first


class RAGEngine:
    def __init__(self, models_dir: Path):
        self.models_dir = models_dir
        self._llama = None
        self._llama_chat_supported = False
        self._provider = os.getenv("LOCALMIND_LLM_PROVIDER", "auto").strip().lower() or "auto"
        self._openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._openai_model = os.getenv("OPENAI_MODEL", "gpt-5.4").strip() or "gpt-5.4"
        self._openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.mode = "extractive-fallback"
        self._configure_llm()

    def _configure_llm(self) -> None:
        if self._provider == "openai":
            if self._openai_api_key:
                self.mode = f"openai:{self._openai_model}"
                return
            self.mode = "extractive-fallback"
            return

        self._load_local_llm()
        if self.mode == "llama-cpp":
            return

        if self._provider == "local":
            self.mode = "extractive-fallback"
            return

        if self._openai_api_key:
            self.mode = f"openai:{self._openai_model}"
            return

    def _load_local_llm(self) -> None:
        gguf_files = sorted(self.models_dir.glob("*.gguf"))
        if not gguf_files:
            self.mode = "extractive-fallback"
            return
        try:
            from llama_cpp import Llama  # type: ignore

            model_path = str(gguf_files[0])
            kwargs = {
                "model_path": model_path,
                "n_ctx": 4096,
                "n_threads": max(1, (os.cpu_count() or 4) // 2),
                "verbose": False,
                "n_gpu_layers": 0,
            }
            if "qwen" in gguf_files[0].name.lower():
                kwargs["chat_format"] = "chatml"
            self._llama = Llama(**kwargs)
            self._llama_chat_supported = hasattr(self._llama, "create_chat_completion")
            self.mode = "llama-cpp"
        except Exception:
            self._llama = None
            self._llama_chat_supported = False
            self.mode = "extractive-fallback"

    def _build_openai_messages(self, question: str, sources: Sequence[Dict[str, str]], answer_mode: str = "answer") -> List[Dict[str, str]]:
        source_blocks: List[str] = []
        for index, source in enumerate(sources, start=1):
            label = _source_label(source)
            source_blocks.append(f"[S{index}] {label}\n{source.get('text', '').strip()}")

        context = "\n\n".join(source_blocks)
        answer_instruction = _local_answer_instruction(question, answer_mode)
        system = (
            "You are LocalMind, a precise research assistant.\n"
            "Use only the provided source text.\n"
            "Answer directly and naturally.\n"
            "Cite claims inline using source markers like [S1] or [S2].\n"
            "If the answer is not supported by the provided sources, say 'Not found in your data.'"
        )
        user = f"QUESTION:\n{question}\n\nSOURCES:\n{context}\n\nFORMAT:\n{answer_instruction}\n\nANSWER:"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _call_openai_chat_completions(self, messages: Sequence[Dict[str, str]]) -> str:
        payload = json.dumps(
            {
                "model": self._openai_model,
                "messages": list(messages),
                "temperature": 0.2,
                "max_completion_tokens": 700,
            }
        ).encode("utf-8")
        req = request.Request(
            url=f"{self._openai_base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=45) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenAI request failed: {detail or exc.reason}") from exc
        except Exception as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        data = json.loads(raw)
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "\n".join(part.strip() for part in parts if part.strip()).strip()
        return ""

    def _call_local_chat(self, question: str, sources: Sequence[Dict[str, str]], answer_mode: str = "answer") -> str:
        if self._llama is None:
            return ""

        evidence = _build_local_evidence(question, sources)
        if not evidence:
            return ""

        answer_instruction = _local_answer_instruction(question, answer_mode)
        if self._llama_chat_supported:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are LocalMind, a precise offline assistant. "
                        "Use only the evidence below and never invent facts. "
                        "Do not say 'based on the provided sources'. "
                        "Cite factual claims inline with markers like [S1]. "
                        "If the evidence is insufficient, answer exactly: Not found in your data."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"QUESTION:\n{question}\n\n"
                        f"EVIDENCE:\n{evidence}\n\n"
                        f"FORMAT:\n{answer_instruction}\n\n"
                        "ANSWER:"
                    ),
                },
            ]
            response = self._llama.create_chat_completion(
                messages=messages,
                temperature=0.1,
                top_p=0.85,
                repeat_penalty=1.08,
                max_tokens=420,
            )
            choices = response.get("choices") or []
            if not choices:
                return ""
            message = choices[0].get("message") or {}
            content = message.get("content")
            return _clean_generated_answer(content) if isinstance(content, str) else ""

        prompt = (
            "You are LocalMind, a precise offline assistant.\n"
            "Use only the evidence below and never invent facts.\n"
            "Do not say 'based on the provided sources'.\n"
            "Cite factual claims inline like [S1].\n"
            "If the evidence is insufficient, answer exactly: Not found in your data.\n\n"
            f"QUESTION:\n{question}\n\n"
            f"EVIDENCE:\n{evidence}\n\n"
            f"FORMAT:\n{answer_instruction}\n\n"
            "ANSWER:"
        )
        response = self._llama(
            prompt,
            max_tokens=420,
            temperature=0.1,
            top_p=0.85,
            repeat_penalty=1.08,
            stop=["QUESTION:", "EVIDENCE:", "<|im_end|>"],
        )
        choices = response.get("choices") or []
        if not choices:
            return ""
        text = choices[0].get("text")
        return _clean_generated_answer(text) if isinstance(text, str) else ""

    def generate_answer(self, question: str, sources: List[Dict[str, str]], answer_mode: str = "answer") -> str:
        answer_mode = _normalize_answer_mode(answer_mode)
        context_blocks: List[str] = []
        for src in sources:
            label = f"{src.get('source_file', 'unknown')}#{src.get('chunk_id', 'chunk')}"
            text = src.get("text", "")
            context_blocks.append(f"[{label}] {text}")
        context = "\n\n".join(context_blocks)
        if not context.strip():
            return "Not found in your data."

        if self.mode.startswith("openai:"):
            try:
                text = self._call_openai_chat_completions(self._build_openai_messages(question, sources, answer_mode))
                if text:
                    return text
            except Exception:
                pass

        if self.mode == "llama-cpp" and self._llama is not None:
            try:
                text = self._call_local_chat(question, sources, answer_mode)
                if text:
                    if text == "Not found in your data.":
                        return text
                    if not _has_citation(text):
                        appendix = _grounding_appendix(question, sources)
                        if appendix:
                            return f"{text}\n\n{appendix}"
                    return text
            except Exception:
                pass

        return extractive_answer(question=question, sources=sources, answer_mode=answer_mode)
