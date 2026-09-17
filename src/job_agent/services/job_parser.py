from __future__ import annotations

import re
from collections import OrderedDict

from job_agent.domain.jobs import (
    ParsedJobDescription,
    ParsedJobRequirement,
    RequirementImportance,
    RequirementKind,
    RequirementSkillMode,
    RequirementType,
    WorkArrangement,
)
from job_agent.domain.models import Skill
from job_agent.domain.retrieval import normalize_term


_SECTION_PATTERNS: list[tuple[re.Pattern[str], tuple[RequirementType, RequirementImportance]]] = [
    (
        re.compile(
            r"^(required|requirements?|qualifications?|basic qualifications?|minimum qualifications?|"
            r"what you(?:'|’)ll need|what we(?:'|’)re looking for|you have|who you are)\b",
            re.I,
        ),
        (RequirementType.QUALIFICATION, RequirementImportance.REQUIRED),
    ),
    (
        re.compile(r"^(preferred|nice to have|bonus|desired|preferred qualifications?)\b", re.I),
        (RequirementType.PREFERRED, RequirementImportance.PREFERRED),
    ),
    (
        re.compile(r"^(responsibilities|what you(?:'|’)ll do|the role|your impact|you will)\b", re.I),
        (RequirementType.RESPONSIBILITY, RequirementImportance.CONTEXT),
    ),
]

_IGNORE_SECTION_PATTERNS = [
    re.compile(r"^(benefits?|perks?|what we offer|compensation|salary|pay range|total rewards)\b", re.I),
    re.compile(r"^(equal opportunity|eeo|diversity|privacy notice|accommodation)\b", re.I),
    re.compile(r"^(about (?:us|the company)|company overview|why join|our culture)\b", re.I),
]

_BULLET = re.compile(r"^[\s\-*•·▪◦‣]+")
_YEARS = re.compile(r"\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.I)

# These aliases intentionally map JD language onto existing career-taxonomy skills.
# "Offensive Security" is a virtual concept: it is recognized as a requirement but
# deliberately has no automatic evidence mapping, so a dedicated offensive-security
# requirement remains a gap until explicit verified evidence is added to the KB.
_SEMANTIC_PATTERNS: list[tuple[re.Pattern[str], tuple[str, ...], RequirementSkillMode | None]] = [
    (re.compile(r"\b(?:ai\s*/?\s*ml|machine learning|generative ai|genai|llm)\s+security\b", re.I), ("AI/LLM Security",), None),
    (re.compile(r"\b(?:protected health information|phi)\b", re.I), ("Healthcare Security",), None),
    (re.compile(r"\b(?:personally identifiable information|pii)\b", re.I), ("Privacy Engineering", "Data Security"), None),
    (re.compile(r"\bgrc\b|governance[, /-]*risk[, /-]*(?:and )?compliance", re.I), ("Security Governance", "Risk Management", "Compliance"), None),
    (re.compile(r"\b(?:blue team|secops|security operations?)\b", re.I), ("Security Monitoring", "Incident Response"), RequirementSkillMode.ANY),
    (re.compile(r"\b(?:red team|offensive security|penetration testing|penetration tests?|pentest|bug bounty)\b", re.I), ("Offensive Security",), None),
    (re.compile(r"\bcode review\b", re.I), ("Secure Coding",), None),
    (re.compile(r"\bvulnerability discovery\b", re.I), ("Vulnerability Management",), None),
    (re.compile(r"\bregulatory\b", re.I), ("Compliance",), None),
    (re.compile(r"\bprivacy\b", re.I), ("Privacy Engineering",), None),
    (re.compile(r"\bcustomer trust\b", re.I), ("Customer Security",), None),
    (re.compile(r"\bfast[- ]paced\b.*\b(?:release|releases|deployment|deployments)\b", re.I), ("Release Engineering",), None),
    (re.compile(r"\btechnical and non[- ]technical stakeholders\b|\bstakeholder(?:s)?\b", re.I), ("Business Risk Translation", "Technical Consulting"), RequirementSkillMode.ANY),
    (re.compile(r"\bstrateg(?:ic|ically)\b.*\bhands[- ]on\b|\bhands[- ]on\b.*\bstrateg(?:ic|ically)\b", re.I), ("Strategy", "Technical Leadership"), None),
    (re.compile(r"\bsetting strategy\b|\bsecurity strategy\b", re.I), ("Strategy",), None),
    (re.compile(r"\bmanaging roadmaps?\b|\bacross multiple teams\b", re.I), ("Technical Leadership",), None),
    (re.compile(r"\bmodern systems are attacked\b|\battacker mindset\b", re.I), ("Threat Modeling", "Security Architecture"), RequirementSkillMode.ANY),
]

_NON_REQUIREMENT_PATTERNS = [
    re.compile(r"\bbase salary range\b|\btotal compensation\b|\bcompensation is based\b", re.I),
    re.compile(r"\b401\s*\(?k\)?\b|\bhealth,? dental|\bvision coverage\b", re.I),
    re.compile(r"\bfree therapy\b|\bwellness\b|\bhardware or software that will make you happy\b", re.I),
    re.compile(r"\bawesome community of co[- ]workers\b|\bchanges lives\b", re.I),
]


class DeterministicJobParser:
    """Conservative JD parser with explicit section and requirement semantics."""

    def __init__(self, skills: list[Skill]) -> None:
        self.skills = skills
        self._taxonomy_names = {skill.name for skill in skills}
        self._aliases = self._build_aliases(skills)

    def parse(self, title: str, description: str, location: str | None = None) -> ParsedJobDescription:
        current_type = RequirementType.OTHER
        current_importance = RequirementImportance.CONTEXT
        current_section: str | None = None
        ignore_section = False
        requirements: list[ParsedJobRequirement] = []
        discovered: OrderedDict[str, None] = OrderedDict()
        ordinal = 0

        for raw_line in description.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            ignored_header = self._ignored_header(line)
            if ignored_header:
                ignore_section = True
                current_section = line.rstrip(":")[:120]
                current_type = RequirementType.OTHER
                current_importance = RequirementImportance.CONTEXT
                continue

            header = self._header(line)
            if header is not None:
                ignore_section = False
                current_type, current_importance = header
                current_section = line.rstrip(":")[:120]
                continue

            if ignore_section:
                continue

            text = _BULLET.sub("", line).strip()
            if len(text) < 8 or self._non_requirement_line(text):
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

            canonical_skills, forced_mode = self._skills_in_text(text)
            for name in canonical_skills:
                discovered.setdefault(name, None)

            years_match = _YEARS.search(text)
            minimum_years = int(years_match.group(1)) if years_match else None
            requirement_kind = self._requirement_kind(text, minimum_years, canonical_skills)
            skill_match_mode = forced_mode or self._skill_match_mode(text, canonical_skills)

            meaningful = (
                current_type is not RequirementType.OTHER
                or canonical_skills
                or minimum_years is not None
                or any(
                    word in lower
                    for word in (
                        "experience",
                        "knowledge",
                        "ability",
                        "proficient",
                        "expertise",
                        "background",
                        "lead",
                        "strategy",
                    )
                )
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
                    requirement_kind=requirement_kind,
                    skill_match_mode=skill_match_mode,
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
    def _ignored_header(line: str) -> bool:
        cleaned = line.rstrip(":").strip()
        if len(cleaned) > 90:
            return False
        return any(pattern.search(cleaned) for pattern in _IGNORE_SECTION_PATTERNS)

    @staticmethod
    def _non_requirement_line(text: str) -> bool:
        return any(pattern.search(text) for pattern in _NON_REQUIREMENT_PATTERNS)

    @staticmethod
    def _build_aliases(skills: list[Skill]) -> list[tuple[str, str]]:
        aliases: list[tuple[str, str]] = []
        for skill in skills:
            candidates = {skill.name, *skill.aliases}
            for candidate in candidates:
                normalized = normalize_term(candidate)
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

    def _skills_in_text(self, text: str) -> tuple[list[str], RequirementSkillMode | None]:
        normalized = f" {normalize_term(text)} "
        found: OrderedDict[str, None] = OrderedDict()
        forced_mode: RequirementSkillMode | None = None
        for alias, canonical in self._aliases:
            if f" {alias} " in normalized or (" " in alias and alias in normalized):
                found.setdefault(canonical, None)

        for pattern, concepts, mode in _SEMANTIC_PATTERNS:
            if not pattern.search(text):
                continue
            for concept in concepts:
                # Existing taxonomy concepts plus a small number of intentional virtual
                # concepts are allowed. Virtual concepts resolve to a transparent gap.
                if concept in self._taxonomy_names or concept == "Offensive Security":
                    found.setdefault(concept, None)
            if mode is not None:
                forced_mode = mode
        return list(found), forced_mode

    @staticmethod
    def _requirement_kind(
        text: str, minimum_years: int | None, canonical_skills: list[str]
    ) -> RequirementKind:
        lower = text.lower()
        if minimum_years is not None and "leadership" in lower and "security" in lower:
            return RequirementKind.LEADERSHIP_YEARS
        if minimum_years is not None:
            return RequirementKind.EXPERIENCE_YEARS
        if "strateg" in lower and "hands-on" in lower:
            return RequirementKind.OPERATING_MODEL
        if canonical_skills:
            return RequirementKind.SKILL
        return RequirementKind.OTHER

    @staticmethod
    def _skill_match_mode(text: str, canonical_skills: list[str]) -> RequirementSkillMode:
        if len(canonical_skills) > 1 and re.search(r"\b(?:or|and/or)\b", text, re.I):
            return RequirementSkillMode.ANY
        return RequirementSkillMode.ALL

    @staticmethod
    def _seniority(title: str, description: str) -> str | None:
        haystack = f"{title} {description[:1500]}".lower()
        title_lower = title.lower()
        for label, terms in (
            ("executive", ("chief", "ciso", "vice president", "vp ")),
            ("director", ("director", "head of")),
            ("senior manager", ("senior manager", "sr. manager", "sr manager")),
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
            ("ai_security", ("ai security", "ai/ml security", "llm security", "model security")),
            ("security_engineering", ("security engineer", "security engineering", "head of security engineering")),
            ("security_leadership", ("security director", "director of security", "director of information security", "director of cybersecurity", "head of security", "head of cybersecurity", "security manager")),
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
