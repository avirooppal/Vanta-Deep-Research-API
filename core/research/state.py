from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Finding:
    url: str
    title: str
    facts: str
    round_number: int
    trust_score: int = 50
    contradicts_claim_id: Optional[str] = None

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
    sources: list[ValidatedSource] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    report_md: Optional[str] = None
    citations: list[dict] = field(default_factory=list)
    is_done: bool = False
