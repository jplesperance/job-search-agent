from __future__ import annotations

import re
from collections import OrderedDict

from job_agent.domain.jobs import (
    ParsedJobDescription,
    ParsedJobRequirement,
    RequirementImportance,
    RequirementType,
    WorkArrangement,
)
from job_agent.domain.models import Skill
from job_agent.domain.retrieval import normalize_term


_SECTION_PATTERNS: list[tuple[re.Pattern[str], tuple[RequirementType, RequirementImportance]]] = [
    (re.compile(r"^(required|requirements?|qualifications?|basic qualifications?|minimum qualifications?|what you(?:'|’)ll need|what we(?:'|’)re looking for|you have)\b", re.I),
     (RequirementType.QUALIFICATION, RequirementImportance.REQUIRED)),
    (re.compile(r"^(preferred|nice to have|bonus|desired|preferred qualifications?)\b", re.I),
     (RequirementType.PREFERRED, RequirementImportance.PREFERRED)),
    (re.compile(r"^(responsibilities|what you(?:'|’)ll do|the role|your impact|you will)\b", re.I),
     (RequirementType.RESPONSIBILITY, RequirementImportance.CONTEXT)),
]

_BULLET = re.compile(r"^[\s\-*•·▪◦‣]+")
_YEARS = re.compile(r"\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.I)


class DeterministicJobParser:
    """Conservative JD parser.

    It only canonicalizes skills that already exist in the career taxonomy. Unknown
    requirements remain text requirements and are surfaced as unknowns by matching.
    """

    def __init__(self, skills: list[Skill]) -> None:
        self.skills = skills
        self._aliases = self._build_aliases(skills)

    def parse(self, title: str, description: str, location: str | None = None) -> ParsedJobDescription:
        current_type = RequirementType.OTHER
        current_importance = RequirementImportance.CONTEXT
        current_section: str | None = None
        requirements: list[ParsedJobRequirement] = []
        discovered: OrderedDict[str, None] = OrderedDict()
        ordinal = 0

        for raw_line in description.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            header = self._header(line)
            if header is not None:
                current_type, current_importance = header
                current_section = line.rstrip(":")[:120]
                continue

            text = _BULLET.sub("", line).strip()
            if len(text) < 8:
                continue

            inline_importance = current_importance
            inline_type = current_type
            lower = text.lower()
            if any(token in lower for token in ("preferred", "nice to have", "bonus", "ideally")):
                inline_importance = RequirementImportance.PREFERRED
                inline_type = RequirementType.PREFERRED
            elif any(token in lower for token in ("required", "must have", "must possess", "minimum")):
                inline_importance = RequirementImportance.REQUIRED
                inline_type = RequirementType.QUALIFICATION

            canonical_skills = self._skills_in_text(text)
            for name in canonical_skills:
                discovered.setdefault(name, None)

            years_match = _YEARS.search(text)
            minimum_years = int(years_match.group(1)) if years_match else None

            # Retain lines in meaningful sections, or lines containing an explicit
            # requirement signal / recognized skill. This avoids treating the entire
            # company marketing preamble as a requirement list.
            meaningful = (
                current_type is not RequirementType.OTHER
                or canonical_skills
                or minimum_years is not None
                or any(word in lower for word in ("experience", "knowledge", "ability", "proficient", "expertise"))
            )
            if not meaningful:
                continue

            requirements.append(
                ParsedJobRequirement(
                    ordinal=ordinal,
                    requirement_type=inline_type,
                    importance=inline_importance,
                    text=text,
                    canonical_skills=canonical_skills,
                    minimum_years=minimum_years,
                    source_section=current_section,
                )
            )
            ordinal += 1

        min_years_values = [r.minimum_years for r in requirements if r.minimum_years is not None]
        return ParsedJobDescription(
            role_family=self._role_family(title, description),
            seniority=self._seniority(title, description),
            work_arrangement=self._work_arrangement(title, description, location),
            requirements=requirements,
            discovered_skills=list(discovered),
            minimum_years=max(min_years_values) if min_years_values else None,
        )

    @staticmethod
    def _header(line: str) -> tuple[RequirementType, RequirementImportance] | None:
        cleaned = line.rstrip(":").strip()
        if len(cleaned) > 90:
            return None
        for pattern, value in _SECTION_PATTERNS:
            if pattern.search(cleaned):
                return value
        return None

    @staticmethod
    def _build_aliases(skills: list[Skill]) -> list[tuple[str, str]]:
        aliases: list[tuple[str, str]] = []
        for skill in skills:
            candidates = {skill.name, *skill.aliases}
            for candidate in candidates:
                normalized = normalize_term(candidate)
                # Very short one-token aliases create false positives (notably "Go").
                # Preserve 3-character canonical names/acronyms such as AWS, IAM, API, Git,
                # and digit-bearing aliases such as K8s, while dropping 1-2 character terms.
                if not normalized:
                    continue
                if " " not in normalized and len(normalized) < 4:
                    allow_short = (
                        len(normalized) >= 3
                        and (candidate == skill.name or candidate.isupper() or any(ch.isdigit() for ch in candidate))
                    )
                    if not allow_short:
                        continue
                aliases.append((normalized, skill.name))
        aliases.sort(key=lambda item: (-len(item[0]), item[0]))
        return aliases

    def _skills_in_text(self, text: str) -> list[str]:
        normalized = f" {normalize_term(text)} "
        found: OrderedDict[str, None] = OrderedDict()
        for alias, canonical in self._aliases:
            if f" {alias} " in normalized or (" " in alias and alias in normalized):
                found.setdefault(canonical, None)
        return list(found)

    @staticmethod
    def _seniority(title: str, description: str) -> str | None:
        haystack = f"{title} {description[:1500]}".lower()
        # Title has stronger signal; order from most specific/highest first.
        title_lower = title.lower()
        for label, terms in (
            ("executive", ("chief", "ciso", "vice president", "vp ")),
            ("director", ("director", "head of")),
            ("principal", ("principal",)),
            ("staff", ("staff",)),
            ("lead", ("lead",)),
            ("senior", ("senior", "sr.")),
            ("manager", ("manager",)),
            ("mid", ("engineer ii", "architect ii")),
            ("junior", ("junior", "entry level", "associate")),
        ):
            if any(term in title_lower for term in terms):
                return label
        if "senior level" in haystack:
            return "senior"
        return None

    @staticmethod
    def _role_family(title: str, description: str) -> str:
        haystack = f"{title} {description[:2500]}".lower()
        title_lower = title.lower()
        families = (
            ("application_security", ("application security", "appsec", "product security")),
            ("security_architecture", ("security architect", "security architecture")),
            ("cloud_security", ("cloud security", "infrastructure security")),
            ("ai_security", ("ai security", "llm security", "model security")),
            ("security_engineering", ("security engineer", "security engineering")),
            ("security_leadership", ("security director", "director of security", "head of security")),
        )
        for family, terms in families:
            if any(term in title_lower for term in terms):
                return family
        for family, terms in families:
            if any(term in haystack for term in terms):
                return family
        return "other"

    @staticmethod
    def _work_arrangement(title: str, description: str, location: str | None = None) -> WorkArrangement:
        haystack = f"{title} {location or ''} {description[:2500]}".lower()
        if re.search(r"\bhybrid\b", haystack):
            return WorkArrangement.HYBRID
        if re.search(r"\b(remote|work from home|distributed)\b", haystack):
            return WorkArrangement.REMOTE
        if re.search(r"\b(on[- ]?site|in office|office-based)\b", haystack):
            return WorkArrangement.ONSITE
        return WorkArrangement.UNKNOWN
