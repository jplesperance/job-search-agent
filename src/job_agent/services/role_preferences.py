from __future__ import annotations

import re
from dataclasses import dataclass

from job_agent.domain.models import TargetingPolicy


_SECURITY_TITLE_TERMS = (
    "security",
    "cybersecurity",
    "cyber security",
    "information security",
    "infosec",
    "appsec",
    "application security",
    "product security",
    "cloud security",
    "ai security",
    "ml security",
    "red team",
    "offensive security",
    "vulnerability",
    "incident response",
    "detection and response",
    "detection & response",
    "threat intelligence",
    "threat modeling",
    "identity and access management",
    "identity access management",
    "iam",
    "grc",
)

_NON_CYBER_TITLE_TERMS = (
    "security guard",
    "physical security",
    "loss prevention",
    "public safety",
)

_SOFTWARE_ENGINEERING_TITLE_TERMS = (
    "software engineer",
    "software engineering",
    "software developer",
    "backend engineer",
    "front end engineer",
    "frontend engineer",
    "full stack engineer",
    "full-stack engineer",
)

# These are deliberately conservative. Security roles often use Python/Go for automation,
# so a single programming-language mention is not enough to classify the role as coding-heavy.
_HEAVY_CODING_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\bwrite(?:s|ing)?\s+(?:and\s+maintain\s+)?production\s+code\b", re.I), 3),
    (re.compile(r"\bhands[- ]on\s+coding\b", re.I), 3),
    (re.compile(r"\bsoftware\s+(?:engineering|development)\s+(?:experience|background)\b", re.I), 2),
    (re.compile(r"\b\d+\+?\s+years?[^\n]{0,60}\bsoftware\s+(?:engineering|development)\b", re.I), 3),
    (re.compile(r"\bbuild(?:ing)?\s+and\s+maintain(?:ing)?\s+(?:production\s+)?(?:software|services|platforms?)\b", re.I), 2),
    (re.compile(r"\bdesign(?:ing)?\s+and\s+implement(?:ing)?[^\n]{0,80}\bsoftware\b", re.I), 2),
    (re.compile(r"\bstrong\s+(?:software\s+)?programming\s+(?:skills|experience)\b", re.I), 2),
    (re.compile(r"\bcoding\s+(?:skills|experience|interview)\b", re.I), 2),
    (re.compile(r"\bproficien(?:cy|t)\s+(?:in|with)\s+(?:python|go|golang|java|rust|c\+\+|typescript)\b", re.I), 1),
    (re.compile(r"\bdevelop(?:ing)?\s+(?:and\s+maintain(?:ing)?\s+)?security\s+tooling\b", re.I), 1),
)


@dataclass(frozen=True)
class RolePreferenceDecision:
    accepted: bool
    rationale: str
    heavy_coding_score: int = 0


def has_security_title_signal(title: str) -> bool:
    lower = re.sub(r"\s+", " ", title.lower()).strip()
    if any(term in lower for term in _NON_CYBER_TITLE_TERMS):
        return False
    return any(term in lower for term in _SECURITY_TITLE_TERMS)


def _title_overlap(candidate: str, target: str) -> bool:
    stop = {
        "of", "and", "the", "senior", "sr", "lead", "staff", "principal",
        "manager", "director", "head", "member", "technical",
    }
    candidate_tokens = {token for token in re.findall(r"[a-z0-9]+", candidate) if token not in stop}
    target_tokens = {token for token in re.findall(r"[a-z0-9]+", target) if token not in stop}
    # Overlap is only useful after the candidate has demonstrated a security-domain signal.
    return bool(candidate_tokens and target_tokens and len(candidate_tokens & target_tokens) >= 2)


def heavy_coding_score(description: str | None) -> int:
    if not description:
        return 0
    score = 0
    for pattern, weight in _HEAVY_CODING_PATTERNS:
        if pattern.search(description):
            score += weight
    return score


def evaluate_role_preferences(
    *,
    title: str,
    description: str | None,
    policy: TargetingPolicy | None,
) -> RolePreferenceDecision:
    lower = re.sub(r"\s+", " ", title.lower()).strip()

    if any(term in lower for term in _NON_CYBER_TITLE_TERMS):
        return RolePreferenceDecision(False, "non-cyber/physical-security title")

    excluded_title_terms = set(policy.excluded_title_terms) if policy else set()
    for term in sorted(excluded_title_terms):
        if term.lower() in lower:
            return RolePreferenceDecision(False, f"excluded title term present: {term}")

    security_signal = has_security_title_signal(title)
    target_overlap = False
    if policy and security_signal:
        target_overlap = any(_title_overlap(lower, target.lower()) for target in policy.target_titles)

    if not security_signal and not target_overlap:
        return RolePreferenceDecision(False, "no security-title signal")

    if policy and policy.exclude_software_engineering_roles:
        if any(term in lower for term in _SOFTWARE_ENGINEERING_TITLE_TERMS):
            return RolePreferenceDecision(False, "software-engineering title excluded by policy")

    coding_score = heavy_coding_score(description)
    if policy and policy.exclude_heavy_coding_roles and coding_score >= 4:
        return RolePreferenceDecision(
            False,
            f"coding-heavy role excluded by policy (signal score={coding_score})",
            heavy_coding_score=coding_score,
        )

    return RolePreferenceDecision(True, "security role accepted", heavy_coding_score=coding_score)
