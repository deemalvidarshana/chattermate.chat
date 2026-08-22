"""Deterministic cleanup, chunking and passage selection for knowledge text.

Website readers are intentionally tolerant because many sites have unusual DOMs.
That tolerance must not leak whole 40k-character pages into an LLM tool result:
provider context/TPM limits are much smaller than the vector store.  The helpers
in this module keep indexing and retrieval bounded without depending on an LLM.
"""

from __future__ import annotations

import re
from typing import Iterable, List


DEFAULT_INDEX_CHUNK_CHARS = 1800
DEFAULT_INDEX_OVERLAP_CHARS = 180
DEFAULT_PASSAGE_CHARS = 1400

_BOILERPLATE_LINES = {
    "skip to content",
    "search",
    "close",
    "menu",
    "open menu",
    "previous",
    "next",
    "back to top",
    "all rights reserved",
}

_QUERY_STOP_WORDS = {
    "about", "after", "also", "and", "are", "can", "could", "does",
    "for", "from", "give", "have", "how", "into", "its", "more",
    "our", "please", "provide", "tell", "that", "the", "their", "them",
    "there", "these", "they", "this", "those", "what", "when", "where",
    "which", "with", "would", "you", "your",
}


def clean_knowledge_text(content: str) -> str:
    """Remove obvious crawler boilerplate while preserving factual text/URLs."""
    if not content:
        return ""

    text = content.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    # Browser/map widgets often inline entire percent-encoded SVG files in
    # markdown image URLs. They contain no searchable knowledge and can be
    # several thousand characters long.
    text = re.sub(r"!\[[^\]]*\]\(data:image/[^)]*\)", " ", text, flags=re.I)

    kept: List[str] = []
    previous_key = None
    for raw_line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            if kept and kept[-1] != "":
                kept.append("")
            continue

        # Drop image-only markdown and common chrome controls. Link-bearing
        # factual lines are retained because product/contact URLs are useful.
        if re.fullmatch(r"!\[[^\]]*\]\([^)]*\)", line):
            continue
        plain = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        plain = re.sub(r"[#*_`>|]+", " ", plain)
        key = re.sub(r"\s+", " ", plain).strip().lower().rstrip(".:—-")
        if key in _BOILERPLATE_LINES:
            continue
        if key == previous_key:
            continue

        kept.append(line)
        previous_key = key

    cleaned = "\n".join(kept)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def _hard_split(text: str, max_chars: int) -> List[str]:
    """Split one oversized paragraph, preferring sentence/word boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\[])", text)
    pieces: List[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            words = sentence.split()
            for word in words:
                if len(word) > max_chars:
                    if current:
                        pieces.append(current)
                        current = ""
                    pieces.extend(
                        word[start : start + max_chars]
                        for start in range(0, len(word), max_chars)
                    )
                    continue
                candidate = f"{current} {word}".strip()
                if current and len(candidate) > max_chars:
                    pieces.append(current)
                    current = word
                else:
                    current = candidate
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _units(content: str, max_chars: int) -> Iterable[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|(?=^#{1,6}\s)", content, flags=re.M) if p.strip()]
    if len(paragraphs) == 1 and len(paragraphs[0]) > max_chars:
        # BeautifulSoup's text path may be a single line. Sentence splitting
        # still yields bounded chunks in that case.
        yield from _hard_split(paragraphs[0], max_chars)
        return
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            yield paragraph
        else:
            yield from _hard_split(paragraph, max_chars)


def split_knowledge_text(
    content: str,
    *,
    max_chars: int = DEFAULT_INDEX_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_INDEX_OVERLAP_CHARS,
) -> List[str]:
    """Return clean, bounded chunks with a small context overlap."""
    if max_chars < 200:
        raise ValueError("max_chars must be at least 200")
    overlap_chars = max(0, min(overlap_chars, max_chars // 3))
    cleaned = clean_knowledge_text(content)
    if not cleaned:
        return []

    chunks: List[str] = []
    current = ""
    for unit in _units(cleaned, max_chars):
        candidate = f"{current}\n\n{unit}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            overlap = current[-overlap_chars:].lstrip() if overlap_chars else ""
            # Avoid starting in the middle of a word.
            if overlap and " " in overlap:
                overlap = overlap.split(" ", 1)[1]
            current = f"{overlap}\n\n{unit}".strip()
            if len(current) > max_chars:
                # A hard-split unit can only overflow because of overlap.
                current = unit
        else:
            current = candidate
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk.strip()]


def query_terms(query: str) -> List[str]:
    terms = re.findall(r"[a-z0-9][a-z0-9_-]{2,}", (query or "").lower())
    return list(dict.fromkeys(term for term in terms if term not in _QUERY_STOP_WORDS))


def select_relevant_passage(
    content: str,
    query: str,
    *,
    max_chars: int = DEFAULT_PASSAGE_CHARS,
) -> str:
    """Select the most query-relevant bounded passage from a legacy full page."""
    candidates = split_knowledge_text(content, max_chars=max_chars, overlap_chars=100)
    if not candidates:
        return ""
    terms = query_terms(query)
    phrase = re.sub(r"\s+", " ", (query or "").strip().lower())

    def score(item: tuple[int, str]) -> tuple[float, int]:
        index, passage = item
        lowered = passage.lower()
        lexical = sum(lowered.count(term) for term in terms)
        phrase_bonus = 5 if phrase and phrase in lowered else 0
        # Navigation-heavy passages often contain dozens of URLs but little
        # prose. Prefer factual passages when lexical relevance is otherwise
        # equal, while keeping URLs in the selected result.
        link_penalty = max(0, lowered.count("http") - 5) * 0.2
        return lexical + phrase_bonus - link_penalty, -index

    return max(enumerate(candidates), key=score)[1][:max_chars].strip()
