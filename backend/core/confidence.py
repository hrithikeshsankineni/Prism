"""
Evidence-grounded confidence scoring.

Confidence is derived from observable signals — corroborating source count,
domain authority, claim category, and cross-agent agreement — rather than
trusting the LLM to self-report a number it has no calibration basis for.

This is the difference between a system that *says* it's confident and one
that has earned the right to be.
"""
from __future__ import annotations

from typing import List
from urllib.parse import urlparse

from backend.schemas.agent_schemas import Finding, Source

# ---------------------------------------------------------------------------
# Domain authority registry
# Higher score = more authoritative = larger positive contribution to confidence
# ---------------------------------------------------------------------------
_DOMAIN_AUTHORITY: dict[str, float] = {
    # Tier 1: primary sources, peer-reviewed, major wire services
    "reuters.com": 0.95,
    "bloomberg.com": 0.95,
    "apnews.com": 0.93,
    "ft.com": 0.92,
    "wsj.com": 0.92,
    "economist.com": 0.91,
    "nature.com": 0.95,
    "science.org": 0.95,
    "arxiv.org": 0.88,
    "pubmed.ncbi.nlm.nih.gov": 0.90,
    "bbc.com": 0.88,
    # Tier 2: reputable general / tech / financial media
    "nytimes.com": 0.82,
    "washingtonpost.com": 0.82,
    "cnbc.com": 0.80,
    "marketwatch.com": 0.78,
    "finance.yahoo.com": 0.75,
    "techcrunch.com": 0.75,
    "wired.com": 0.75,
    "theverge.com": 0.72,
    "forbes.com": 0.72,
    "businessinsider.com": 0.68,
    "seekingalpha.com": 0.68,
    "scholar.google.com": 0.85,
    "sciencedirect.com": 0.90,
}

# Category weight: how much to trust a claim of this type at face value
_CATEGORY_WEIGHT: dict[str, float] = {
    "fact": 1.00,
    "statistic": 0.95,
    "opinion": 0.65,
    "prediction": 0.60,
}


def _domain_authority(url: str) -> float:
    """Return authority score [0, 1] for a URL's domain."""
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
    except Exception:
        return 0.50

    if host in _DOMAIN_AUTHORITY:
        return _DOMAIN_AUTHORITY[host]

    # TLD-level fallback for government and academic domains
    if host.endswith(".gov") or host.endswith(".gov.uk"):
        return 0.90
    if host.endswith(".edu"):
        return 0.85

    return 0.50  # unknown / neutral


def compute_claim_confidence(
    category: str,
    supporting_source_urls: List[str],
    fallback_sources: List[Source],
) -> float:
    """
    Compute evidence-grounded confidence for a single claim.

    Three signals:
      1. Category weight  — facts outweigh opinions
      2. Source count     — more corroborating URLs → higher confidence (saturates at 3)
      3. Domain authority — Reuters > random blog
    """
    base = 0.45

    # Signal 1: category
    cat_weight = _CATEGORY_WEIGHT.get(category.lower(), 0.75)

    # Signal 2: source count (diminishing returns, caps at 3 sources)
    n = len(supporting_source_urls)
    source_bonus = min(n / 3.0, 1.0) * 0.25

    # Signal 3: domain authority
    if supporting_source_urls:
        auths = [_domain_authority(u) for u in supporting_source_urls]
    elif fallback_sources:
        auths = [_domain_authority(s.url) for s in fallback_sources]
    else:
        auths = [0.50]

    avg_authority = sum(auths) / len(auths)
    # Ranges roughly −0.15 to +0.15 relative to neutral 0.5
    authority_bonus = (avg_authority - 0.50) * 0.30

    raw = (base + source_bonus + authority_bonus) * cat_weight
    return round(min(max(raw, 0.05), 0.95), 3)


def compute_agent_confidence(findings: List[Finding], sources: List[Source]) -> float:
    """
    Aggregate claim-level confidences into a single agent-level score.

    Penalises high variance — an agent that found one strong fact and three
    weak opinions should score lower than one that found four solid facts.
    """
    if not findings:
        return 0.0

    scores = [f.confidence for f in findings]
    mean = sum(scores) / len(scores)

    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    consistency_penalty = min(variance * 0.5, 0.10)

    return round(min(max(mean - consistency_penalty, 0.05), 0.95), 3)


def boost_for_corroboration(base_confidence: float, corroborating_agents: int) -> float:
    """
    Lift confidence when independent agents converge on the same claim.

    Each additional agreeing agent contributes diminishing returns:
      +1 agent → +0.06, +2 → +0.11, +3 → +0.15 (cap +0.18)
    """
    if corroborating_agents <= 1:
        return base_confidence
    boost = min((corroborating_agents - 1) * 0.06, 0.18)
    return round(min(base_confidence + boost, 0.97), 3)
