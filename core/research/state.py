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
    claim_type: str = "FACT"
    atomic_claim: Optional[object] = None  # core.research.evidence.models.AtomicClaim


@dataclass
class ValidatedSource:
    url: str
    title: str
    text: str
    trust_score: int
    flags: str
    provenance: Optional[dict] = None
    data_label: str = "UNTRUSTED_EXTERNAL"
    quality: Optional[object] = None   # core.research.evidence.models.SourceQuality
    lineage: Optional[object] = None   # core.research.evidence.models.SourceLineage


@dataclass
class Contradiction:
    description: str
    source_urls: list[str]
    severity: str
    resolution_suggestion: str
    contradiction_type: str = "DIRECT_CONTRADICTION"


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
    # Phase 2: token/request budget (None = unlimited)
    budget: Optional[object] = None  # core.llm.budget.ResearchBudget
    # Phase 6: audit warnings across pipeline execution
    warnings: list[str] = field(default_factory=list)
    # Deep Research upgrade: structured ResearchBrief and ResearchPlan
    brief: Optional[object] = None   # core.research.planning.brief.ResearchBrief
    plan: Optional[object] = None    # core.research.planning.plan.ResearchPlan
    claims: list = field(default_factory=list)  # list[core.research.evidence.models.AtomicClaim]
    challenges: list = field(default_factory=list)  # list[core.research.reasoning.models.ResearchChallenge]
    report_plan: Optional[object] = None  # core.research.synthesis.models.ReportPlan
