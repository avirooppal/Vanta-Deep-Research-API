"""
Vanta Sentinel — Phase 4: Control Plane Policy Enforcement

The Sentinel is the ONLY place where job-level policy is enforced.
It runs synchronously BEFORE a job enters the ARQ queue.

Responsibilities:
  1. Input sanitization — strip/detect prompt-injection patterns
  2. Query policy — length limits, encoding abuse, null-byte injection
  3. URL policy — per-job domain allow/denylist checked before fetch
  4. Job policy — budget limits, round caps from mode config
  5. Model/provider policy — reject unknown providers before any key usage

The Sentinel returns a SentinelVerdict:
  - allowed=True  → job may proceed
  - allowed=False → reason returned to caller; job rejected at the gate

Nothing downstream of the Sentinel should re-validate these properties.
They are architectural guarantees, not optional checks.
"""
from __future__ import annotations

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

# Max query chars accepted from any caller (prevents LLM prompt bombing)
MAX_QUERY_CHARS = 4_000

# Providers the system knows how to route
_KNOWN_PROVIDERS = {
    "openai", "anthropic", "groq", "deepseek", "mistral",
    "together", "xai", "cerebras", "ollama", "ollama_cloud",
    "openrouter", "openai_compatible",
}

# Prompt-injection trigger patterns (case-insensitive)
# Designed to catch the most common jailbreak/prompt-injection templates
# without false-positiving on legitimate research queries.
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I),
    re.compile(r"disregard\s+(your|all)\s+(previous\s+)?(instructions?|rules?|guidelines?)", re.I),
    re.compile(r"you\s+are\s+now\s+(a\s+)?(?!a\s+research)", re.I),
    re.compile(r"act\s+as\s+(a\s+)?(?!a?\s*research)", re.I),
    re.compile(r"system\s*:\s*you\s+are", re.I),
    re.compile(r"</?(system|assistant|user)\s*>", re.I),
    re.compile(r"\[\s*INST\s*\]", re.I),
    re.compile(r"<<\s*SYS\s*>>", re.I),
    re.compile(r"```\s*(system|prompt)\s*\n", re.I),
    re.compile(r"override\s+(safety|content)\s+(filters?|policy|guidelines?)", re.I),
    re.compile(r"reveal\s+(your|the)\s+(system\s+)?prompt", re.I),
    re.compile(r"print\s+(your|the)\s+(system\s+)?prompt", re.I),
    re.compile(r"output\s+(your|the)\s+(system\s+)?prompt", re.I),
]

# Null byte and control character pattern
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class SentinelVerdict:
    allowed: bool
    reason: str = ""
    sanitized_query: str = ""
    injection_signals: list[str] = field(default_factory=list)

    @classmethod
    def allow(cls, sanitized_query: str, signals: list[str] | None = None) -> "SentinelVerdict":
        return cls(allowed=True, sanitized_query=sanitized_query, injection_signals=signals or [])

    @classmethod
    def deny(cls, reason: str) -> "SentinelVerdict":
        return cls(allowed=False, reason=reason)


@dataclass
class UrlVerdict:
    allowed: bool
    reason: str = ""

    @classmethod
    def allow(cls) -> "UrlVerdict":
        return cls(allowed=True)

    @classmethod
    def deny(cls, reason: str) -> "UrlVerdict":
        return cls(allowed=False, reason=reason)


# ---------------------------------------------------------------------------
# Input sanitizer
# ---------------------------------------------------------------------------

def sanitize_query(raw: str) -> SentinelVerdict:
    """
    Validate and sanitize a user research query.

    Returns SentinelVerdict.allow() with the cleaned query, or
    SentinelVerdict.deny() with the rejection reason.

    This does NOT modify LLM prompts — it only validates user-supplied
    query text before it reaches any agent.
    """
    if not raw or not raw.strip():
        return SentinelVerdict.deny("Query must not be empty.")

    # Null-byte / control character injection
    if _CONTROL_CHARS.search(raw):
        return SentinelVerdict.deny("Query contains invalid control characters.")

    # Length enforcement
    if len(raw) > MAX_QUERY_CHARS:
        return SentinelVerdict.deny(
            f"Query exceeds maximum length ({len(raw)} > {MAX_QUERY_CHARS} chars)."
        )

    # Detect injection signals (warn, do not hard-block — research queries can
    # legitimately contain words like "act as an expert" or "ignore X")
    signals: list[str] = []
    for pat in _INJECTION_PATTERNS:
        if pat.search(raw):
            signals.append(pat.pattern)

    # Hard block if ≥ 2 signals detected simultaneously (high confidence attack)
    if len(signals) >= 2:
        logger.warning("Sentinel blocked query with %d injection signals: %s", len(signals), signals)
        return SentinelVerdict.deny(
            "Query contains patterns associated with prompt-injection attacks and was rejected."
        )

    # Strip leading/trailing whitespace; collapse excessive internal whitespace
    cleaned = " ".join(raw.strip().split())

    if signals:
        logger.info("Sentinel detected %d soft injection signal(s) — query allowed with warning", len(signals))

    return SentinelVerdict.allow(cleaned, signals)


# ---------------------------------------------------------------------------
# URL policy checker
# ---------------------------------------------------------------------------

# Deny-by-default private/cloud-metadata subnets (beyond what fetcher already checks)
_DENIED_HOSTS: set[str] = {
    "metadata.google.internal",
    "169.254.169.254",          # AWS/GCP/Azure IMDS
    "fd00:ec2::254",            # AWS IMDS v6
    "100.100.100.200",          # Alibaba Cloud IMDS
    "localhost",
    "127.0.0.1",
    "::1",
}

_DENIED_DOMAINS_SUFFIX: tuple[str, ...] = (
    ".internal",
    ".local",
    ".corp",
    ".lan",
)

# Extension denylist — binary / executable file types the fetcher should not download
_DENIED_EXTENSIONS: set[str] = {
    ".exe", ".dll", ".bat", ".sh", ".ps1", ".bin",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".iso", ".img", ".dmg",
}


def check_url_policy(
    url: str,
    allowed_domains: Optional[set[str]] = None,
    denied_domains: Optional[set[str]] = None,
) -> UrlVerdict:
    """
    Policy-layer URL check, separate from SSRF protection in fetcher.

    allowed_domains: if set, URL must match one of these domains.
    denied_domains:  if set, URL must NOT match any of these.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return UrlVerdict.deny(f"Malformed URL: {url!r}")

    if parsed.scheme not in ("http", "https"):
        return UrlVerdict.deny(f"Only http/https URLs are permitted (got {parsed.scheme!r}).")

    hostname = (parsed.hostname or "").lower()

    if not hostname:
        return UrlVerdict.deny("URL has no hostname.")

    # Hard-denied hostnames
    if hostname in _DENIED_HOSTS:
        return UrlVerdict.deny(f"Host {hostname!r} is on the permanent denylist.")

    # Denied domain suffixes
    for suffix in _DENIED_DOMAINS_SUFFIX:
        if hostname.endswith(suffix):
            return UrlVerdict.deny(f"Host {hostname!r} matches denied suffix {suffix!r}.")

    # IP-based checks (resolves hostname)
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return UrlVerdict.deny(f"Host {hostname!r} resolves to a private/reserved IP: {ip_str}")
    except socket.gaierror:
        pass  # Unresolvable — let fetcher handle (not a sentinel concern)

    # File extension denylist
    path = parsed.path.lower()
    for ext in _DENIED_EXTENSIONS:
        if path.endswith(ext):
            return UrlVerdict.deny(f"URL targets a denied file type ({ext}).")

    # Per-job domain allowlist (if configured)
    if allowed_domains:
        if not any(hostname == d or hostname.endswith(f".{d}") for d in allowed_domains):
            return UrlVerdict.deny(
                f"Host {hostname!r} is not in the allowed-domains list for this job."
            )

    # Per-job domain denylist
    if denied_domains:
        for d in denied_domains:
            if hostname == d or hostname.endswith(f".{d}"):
                return UrlVerdict.deny(f"Host {hostname!r} is on the per-job denylist.")

    return UrlVerdict.allow()


# ---------------------------------------------------------------------------
# Job policy validator (called at job submission time)
# ---------------------------------------------------------------------------

@dataclass
class JobPolicy:
    max_rounds: int = 5
    max_query_chars: int = MAX_QUERY_CHARS
    allowed_providers: Optional[set[str]] = None   # None = any known provider
    allowed_domains: Optional[set[str]] = None     # None = any safe domain
    denied_domains: Optional[set[str]] = None


def validate_job_policy(
    query: str,
    provider: Optional[str],
    requested_rounds: int,
    policy: Optional[JobPolicy] = None,
) -> SentinelVerdict:
    """
    Full job-submission policy check.
    Combines query sanitization + provider check + round cap.
    """
    pol = policy or JobPolicy()

    # 1. Query sanitization
    verdict = sanitize_query(query)
    if not verdict.allowed:
        return verdict

    # 2. Provider check
    if provider and provider not in _KNOWN_PROVIDERS:
        return SentinelVerdict.deny(
            f"Unknown provider {provider!r}. Accepted: {sorted(_KNOWN_PROVIDERS)}"
        )
    if pol.allowed_providers and provider and provider not in pol.allowed_providers:
        return SentinelVerdict.deny(
            f"Provider {provider!r} is not permitted by job policy."
        )

    # 3. Round cap
    if requested_rounds > pol.max_rounds:
        return SentinelVerdict.deny(
            f"Requested rounds ({requested_rounds}) exceeds policy cap ({pol.max_rounds})."
        )

    return SentinelVerdict.allow(verdict.sanitized_query, verdict.injection_signals)
