import re
from datetime import datetime
from urllib.parse import urlparse
from typing import Optional


# ---------------------------------------------------------------------------
# Authoritative / suspicious domain heuristics
# ---------------------------------------------------------------------------

AUTHORITATIVE_DOMAINS = {
    "arxiv.org",
    "nature.com",
    "science.org",
    "sciencedirect.com",
    "nih.gov",
    "cdc.gov",
    "who.int",
    "wikipedia.org",
    "github.com",
    "ieee.org",
    "acm.org",
    "reuters.com",
    "apnews.com",
    "bloomberg.com",
}

AUTHORITATIVE_TLDS = {".edu", ".gov", ".mil", ".ac.uk", ".edu.au"}
SUSPICIOUS_TLDS = {".click", ".top", ".buzz", ".rest", ".gq", ".cf", ".tk", ".work", ".fit"}

BOILERPLATE_REGEX = re.compile(
    r"(accept cookies|cookie policy|privacy policy|terms of service|all rights reserved|sign up for our newsletter|subscribe now|advertisement|share on (twitter|facebook|linkedin))",
    re.IGNORECASE,
)


def heuristic_validate_domain(url: str) -> Optional[tuple[int, str]]:
    """
    Validate a URL by domain and TLD without invoking an LLM.
    Returns (trust_score, flags) or None if domain requires LLM evaluation.
    """
    if not url:
        return (20, "Empty URL")

    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return (20, "Invalid URL hostname")

        for domain in AUTHORITATIVE_DOMAINS:
            if hostname == domain or hostname.endswith("." + domain):
                return (90, "Authoritative Domain (heuristic)")

        for tld in AUTHORITATIVE_TLDS:
            if hostname.endswith(tld):
                return (90, f"Authoritative TLD {tld} (heuristic)")

        for tld in SUSPICIOUS_TLDS:
            if hostname.endswith(tld):
                return (15, f"Low-Quality / Suspicious TLD {tld} (heuristic)")

    except Exception:
        return None

    return None


# ---------------------------------------------------------------------------
# Content compression
# ---------------------------------------------------------------------------

def compress_source_text(text: str, query: str = "", max_chars: int = 3500) -> str:
    """
    Extract high-density, query-relevant content from scraped web text.
    Removes boilerplate, duplicate whitespace, and ranks paragraphs by relevance.
    """
    if not text:
        return ""

    cleaned = re.sub(r"\r\n|\r", "\n", text)
    cleaned = re.sub(r"[ \t]*\n[ \t]*", "\n", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n\n", cleaned).strip()
    cleaned = re.sub(r"[ \t]+", " ", cleaned)

    if len(cleaned) <= max_chars:
        raw_paragraphs = [p.strip() for p in cleaned.split("\n\n") if len(p.strip()) > 30]
        filtered = [p for p in raw_paragraphs if not BOILERPLATE_REGEX.search(p)]
        if filtered:
            res = "\n\n".join(filtered)
            if len(res) > max_chars:
                truncated = res[:max_chars]
                last_para = truncated.rfind("\n\n")
                return truncated[:last_para] if last_para > max_chars * 0.8 else truncated
            return res
        return cleaned

    raw_paragraphs = [p.strip() for p in cleaned.split("\n\n") if len(p.strip()) > 30]
    filtered_paragraphs = [p for p in raw_paragraphs if not BOILERPLATE_REGEX.search(p)]
    if not filtered_paragraphs:
        filtered_paragraphs = raw_paragraphs

    query_words = set(re.findall(r"\w{3,}", query.lower())) if query else set()

    scored_paragraphs = []
    for idx, p in enumerate(filtered_paragraphs):
        p_lower = p.lower()
        score = 0
        if query_words:
            matched_words = sum(1 for w in query_words if w in p_lower)
            score += matched_words * 3
        score += max(0, 5 - idx)
        scored_paragraphs.append((score, idx, p))

    scored_paragraphs.sort(key=lambda x: x[0], reverse=True)

    selected_indices = set()
    total_len = 0
    for _, idx, p in scored_paragraphs:
        if total_len + len(p) + 2 > max_chars:
            continue
        selected_indices.add(idx)
        total_len += len(p) + 2

    if not selected_indices:
        truncated = cleaned[:max_chars]
        last_para = truncated.rfind("\n\n")
        return truncated[:last_para] if last_para > max_chars * 0.8 else truncated

    ordered_paragraphs = [filtered_paragraphs[i] for i in sorted(selected_indices)]
    return "\n\n".join(ordered_paragraphs)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def deduplicate_findings(findings: list, similarity_threshold: float = 0.70) -> list:
    """
    Remove near-identical claims to eliminate context bloat in synthesizer.
    Preserves finding with higher trust score or earlier round.
    """
    if not findings or len(findings) <= 1:
        return findings

    unique_findings = []
    seen_word_sets: list[set[str]] = []

    for f in findings:
        fact_text = f.facts if isinstance(f.facts, str) else str(f.facts)
        # Also include summary if present for better dedup
        summary_text = getattr(f, "summary", "") or ""
        combined = fact_text + " " + summary_text
        words = set(re.findall(r"\w{3,}", combined.lower()))

        if not words:
            continue

        is_duplicate = False
        for existing_set in seen_word_sets:
            if _jaccard_similarity(words, existing_set) >= similarity_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            unique_findings.append(f)
            seen_word_sets.append(words)

    return unique_findings


def compact_system_prompt(prompt: str) -> str:
    """Compact prompt text by removing unnecessary multi-line whitespace and filler."""
    lines = [line.strip() for line in prompt.strip().splitlines() if line.strip()]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Quality filtering (Odysseus-inspired)
# ---------------------------------------------------------------------------

LOW_QUALITY_MARKERS = [
    "insufficient to",
    "content is insufficient",
    "no substantive data",
    "does not contain",
    "not relevant to",
    "no relevant information",
    "unable to extract",
    "completely unrelated",
    "boilerplate",
    "footer text",
    "cookie consent",
    "cookie banner",
    "cookie notice",
    "copyright notice",
    "copyright footer",
    "all rights reserved",
]


def is_low_quality(summary: str) -> bool:
    """Check if a finding summary indicates useless or irrelevant content."""
    try:
        if not isinstance(summary, str) or not summary:
            return True
        low = summary.lower()
        return any(marker in low for marker in LOW_QUALITY_MARKERS)
    except Exception:
        return False  # fail open


# ---------------------------------------------------------------------------
# Reasoning model cleanup (Odysseus-inspired)
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_thinking(text: Optional[str]) -> Optional[str]:
    """Strip <think>...</think> reasoning blocks from LLM output."""
    if text is None:
        return None
    return _THINK_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# Date grounding
# ---------------------------------------------------------------------------

def current_date_context() -> str:
    """
    Preamble that grounds query-generation LLMs in the real current date.
    Prevents models from emitting stale year references in search queries.
    """
    now = datetime.now().astimezone()
    return (
        f"Today's date is {now.strftime('%B %d, %Y')} ({now.strftime('%Y-%m-%d')}). "
        f"When a search query needs a year or refers to 'latest'/'current'/"
        f"'this year', use {now.strftime('%Y')} or relative wording — never a "
        f"year inferred from training data.\n\n"
    )
