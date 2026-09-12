from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ResearchMode(str, Enum):
    RESEARCH = "research"
    STUDY = "study"
    BRIEF = "brief"
    DEEP = "deep"


@dataclass
class ModeConfig:
    name: str
    display_name: str
    description: str
    default_rounds: int
    max_rounds_cap: int
    min_trust_score: int
    search_strategy: str
    extraction_focus: str
    synthesis_prompt: str
    include_study_guide: bool = False


RESEARCH_MODE_CONFIG = ModeConfig(
    name=ResearchMode.RESEARCH.value,
    display_name="Standard Research",
    description="Comprehensive analytical research. Thorough investigation, objective evidence gathering, contradiction analysis, and structured analytical report with inline source citations.",
    default_rounds=3,
    max_rounds_cap=5,
    min_trust_score=30,
    search_strategy="Generate queries targeting latest authoritative sources, empirical analyses, industry reports, and multi-perspective commentary.",
    extraction_focus="Extract verified facts, statistical data, causal claims, empirical outcomes, and source credibility markers.",
    synthesis_prompt="""You are a Lead Research Analyst.
Write a comprehensive, professional analytical report answering the user's research question.
Structure your report with:
1. Executive Summary
2. Background & Context
3. In-Depth Analysis & Key Findings
4. Nuances, Contradictions & Counterarguments (if any)
5. Strategic / Practical Implications
6. Cited Sources

Cite sources inline using [1], [2] notation corresponding to finding numbers.""",
    include_study_guide=False,
)

STUDY_MODE_CONFIG = ModeConfig(
    name=ResearchMode.STUDY.value,
    display_name="Study & Learn",
    description="Educational and pedagogical mode. Explains complex topics from first principles, breaks down core concepts with intuitive analogies, highlights common misconceptions, and provides a knowledge check quiz and glossary.",
    default_rounds=2,
    max_rounds_cap=4,
    min_trust_score=25,
    search_strategy="Generate queries targeting educational guides, first-principles explanations, pedagogical tutorials, foundational definitions, and clear diagrams/examples.",
    extraction_focus="Extract fundamental definitions, core mechanisms, illustrative analogies, common student pitfalls/misconceptions, and key formulas/rules.",
    synthesis_prompt="""You are an Expert Educator and Master Tutor.
Transform the research findings into an engaging, structured study guide answering the user's query.
Use the Feynman technique: explain complex concepts simply, intuitively, and without unnecessary jargon.

Structure the study guide exactly as follows:
# [Topic Title] - Study Guide

## 1. Overview & Learning Objectives
What is this topic, why does it matter, and what will the learner master after reading?

## 2. Core Concepts Explained Simply
Break down foundational principles using clear, everyday analogies and mental models.

## 3. Deep-Dive & Step-by-Step Mechanisms
Walk through the mechanisms, processes, or architecture step by step with concrete examples.

## 4. Common Misconceptions & Pitfalls
Highlight subtle traps, misunderstandings, or frequently confused terms that beginners and practitioners often get wrong.

## 5. Knowledge Check & Practice Questions
Provide 3-5 quiz questions (multiple choice or short answer) followed by an expandable or clear Answer Key with explanations.

## 6. Key Terminology Glossary
A concise table or list defining 5-10 essential terms.

## 7. Next Steps & Recommended Prerequisites
What should the student study next to deepen their mastery?

Cite your sources inline using [1], [2] notation.""",
    include_study_guide=True,
)

BRIEF_MODE_CONFIG = ModeConfig(
    name=ResearchMode.BRIEF.value,
    display_name="Executive Brief",
    description="Rapid high-signal briefing. Delivers Bottom Line Up Front (BLUF), top takeaways, and critical decisions in 1-2 quick rounds.",
    default_rounds=1,
    max_rounds_cap=2,
    min_trust_score=20,
    search_strategy="Generate queries focused on high-level summaries, key metrics, latest status, and direct bottom-line answers.",
    extraction_focus="Extract core answers, high-impact numbers, primary takeaways, and critical decision points.",
    synthesis_prompt="""You are an Executive Intelligence Officer.
Deliver a razor-sharp, high-signal executive briefing answering the user's query.
Omit fluff, throat-clearing, and verbose filler.

Structure your brief as follows:
# Executive Brief: [Topic]

## Bottom Line Up Front (BLUF)
2-3 punchy sentences giving the core answer and immediate significance.

## Key Takeaways
- Bulleted list of the top 3-5 critical findings with hard data or direct evidence.

## Strategic Implications & Action Items
What decisions or actions should be taken based on these findings?

## Sources
Cite your sources inline using [1], [2] notation.""",
    include_study_guide=False,
)

DEEP_MODE_CONFIG = ModeConfig(
    name=ResearchMode.DEEP.value,
    display_name="Deep Academic & Technical",
    description="Exhaustive academic deep dive. Maximizes search rounds, targets academic literature and technical whitepapers, applies strict source validation, and cross-checks claim contradictions.",
    default_rounds=4,
    max_rounds_cap=5,
    min_trust_score=40,
    search_strategy="Generate advanced technical queries targeting peer-reviewed literature, arXiv papers, technical whitepapers, GitHub repositories, RFCs, and specialized domain analyses.",
    extraction_focus="Extract formal technical specifications, rigorous empirical evidence, edge cases, methodology limitations, and conflicting experimental data.",
    synthesis_prompt="""You are a Distinguished Academic Researcher and Technical Fellow.
Produce an exhaustive, rigorous research monograph answering the research inquiry.

Structure your monograph as follows:
# [Formal Title]: An Exhaustive Technical Monograph

## Abstract
Concise formal abstract summarizing inquiry, methodology, synthesis, and key conclusions.

## 1. Technological & Academic Landscape
Historical context, state of the art, and current paradigm.

## 2. Comprehensive Multi-Faceted Analysis
Deep technical breakdown across architectural, mathematical, empirical, or operational dimensions.

## 3. Contradiction & Consensus Matrix
Where do authoritative sources agree, where do they diverge, and what explains the discrepancy?

## 4. Technical Limitations & Open Research Questions
Known bottlenecks, unresolved challenges, and frontier research directions.

## 5. Conclusion & Forward Outlook
Synthesis of trajectory and definitive conclusions.

## 6. Citations & References
Cite sources rigorously inline using [1], [2] notation.""",
    include_study_guide=False,
)

MODE_REGISTRY: dict[str, ModeConfig] = {
    ResearchMode.RESEARCH.value: RESEARCH_MODE_CONFIG,
    ResearchMode.STUDY.value: STUDY_MODE_CONFIG,
    ResearchMode.BRIEF.value: BRIEF_MODE_CONFIG,
    ResearchMode.DEEP.value: DEEP_MODE_CONFIG,
}


def get_mode_config(mode: Optional[str]) -> ModeConfig:
    """Resolve ModeConfig by name, fallback to standard research mode if invalid or None."""
    if not mode:
        return RESEARCH_MODE_CONFIG
    normalized = mode.strip().lower()
    return MODE_REGISTRY.get(normalized, RESEARCH_MODE_CONFIG)


def list_available_modes() -> list[dict]:
    """Return list of serialized mode metadata for API and CLI consumption."""
    return [
        {
            "mode": cfg.name,
            "display_name": cfg.display_name,
            "description": cfg.description,
            "default_rounds": cfg.default_rounds,
            "max_rounds_cap": cfg.max_rounds_cap,
            "min_trust_score": cfg.min_trust_score,
            "include_study_guide": cfg.include_study_guide,
        }
        for cfg in MODE_REGISTRY.values()
    ]


# ---------------------------------------------------------------------------
# Category-aware format overrides (Odysseus-inspired)
# Applied orthogonally to modes during final report generation.
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {"product", "comparison", "howto", "factcheck"}

CATEGORY_CLASSIFICATION_PROMPT = (
    "Classify this research question into exactly ONE category.\n"
    "Categories: product, comparison, howto, factcheck\n"
    "If none fit well, respond with: general\n\n"
    "Question: {question}\n\n"
    "Respond with ONLY the category name, nothing else."
)
