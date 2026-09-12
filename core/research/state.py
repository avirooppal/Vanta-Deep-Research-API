from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Finding:
    url: str
    title: str
    facts: str                      # raw extracted text / backward compat
    round_number: int
    trust_score: int = 50
    contradicts_claim_id: Optional[str] = None
    # Goal-based structured extraction (Odysseus-inspired)
    rational: str = ""              # why this section relates to the goal
    evidence: str = ""              # full original quotes / context
    summary: str = ""               # concise answer to the research goal


@dataclass
class ValidatedSource:
    url: str
    title: str
    text: str
    trust_score: int
    flags: str


@dataclass
class Contradiction:
    description: str
    source_urls: list[str]
    severity: str
    resolution_suggestion: str


@dataclass
class ResearchState:
    question: str
    max_rounds: int
    current_round: int = 1
    queries: list[str] = field(default_factory=list)
    queries_used: set = field(default_factory=set)      # dedup across rounds
    sources: list[ValidatedSource] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    report_md: Optional[str] = None
    evolving_report: str = ""       # incrementally updated report per round
    research_plan: str = ""         # LLM-generated plan (sub-questions, topics)
    category: Optional[str] = None  # auto-detected: product/comparison/howto/factcheck
    citations: list[dict] = field(default_factory=list)
    is_done: bool = False
    mode: str = "research"
    mode_config: Optional[object] = None
