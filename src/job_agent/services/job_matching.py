from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from job_agent.domain.enums import ApprovalStatus, VerificationStatus
from job_agent.domain.jobs import (
    JobIngestRequest,
    JobIngestResponse,
    JobMatchRequest,
    JobMatchResponse,
    LocationCompensationDecision,
    MatchConfidence,
    ParsedJobDescription,
    ParsedJobRequirement,
    RequirementCoverage,
    RequirementImportance,
    RequirementKind,
    RequirementSkillMode,
    WorkArrangement,
)
from job_agent.domain.models import JobAnalysis, JobOpportunity, ScoreComponent, TargetingPolicy
from job_agent.domain.retrieval import EvidenceSearchRequest, MatchMode, RetrievalScope, normalize_term
from job_agent.repositories.interfaces import CareerRepository, JobRepository, PolicyRepository
from job_agent.scoring.hard_filters import evaluate_hard_filters
from job_agent.services.evidence_search import EvidenceSearchService
from job_agent.services.job_parser import DeterministicJobParser
from job_agent.services.location_policy import evaluate_location_compensation, extract_base_salary_range


_DEFAULT_WEIGHTS = {
    "requirements": 0.60,
    "title": 0.15,
    "seniority": 0.10,
    "role_family": 0.15,
}

_REQUIREMENT_WEIGHTS = {
    RequirementImportance.REQUIRED: 3.0,
    RequirementImportance.PREFERRED: 1.5,
    RequirementImportance.CONTEXT: 0.0,
}

_SECURITY_TENURE_SKILLS = (
    "Application Security",
    "Product Security",
    "Security Architecture",
    "Cloud Security",
    "DevSecOps",
    "Vulnerability Management",
    "Incident Response",
    "Detection Engineering",
    "Security Monitoring",
    "Security Governance",
    "Risk Management",
    "Compliance",
    "Data Security",
    "Network Security",
    "Cryptography",
    "IAM Architecture",
)

_LEADERSHIP_SKILLS = (
    "People Leadership",
    "Technical Leadership",
    "Engineering Management",
    "Team Building",
    "Strategy",
    "Security Governance",
)


@dataclass(frozen=True)
class _RequirementMatch:
    coverage: RequirementCoverage
    evidence_uuids: tuple[UUID, ...]


class JobIngestionService:
    def __init__(self, job_repo: JobRepository, career_repo: CareerRepository) -> None:
        self.job_repo = job_repo
        self.career_repo = career_repo

    def ingest(self, request: JobIngestRequest) -> JobIngestResponse:
        content_hash = hashlib.sha256(request.description_raw.encode("utf-8")).hexdigest()
        compensation = request.compensation_text
        if not compensation:
            low, high = extract_base_salary_range(request.description_raw)
            if low is not None and high is not None:
                compensation = f"${low:,.0f} - ${high:,.0f} base"

        job = JobOpportunity(
            source=request.source,
            external_id=request.external_id,
            source_url=request.source_url,
            company=request.company.strip(),
            title=request.title.strip(),
            location=request.location.strip() if request.location else None,
            compensation_text=compensation,
            work_arrangement=request.work_arrangement.value if request.work_arrangement else None,
            description_raw=request.description_raw,
        )
        persisted, created = self.job_repo.upsert(job, content_hash)
        parser = DeterministicJobParser(self.career_repo.list_skills())
        parsed = parser.parse(persisted.title, persisted.description_raw, persisted.location)
        if persisted.work_arrangement:
            try:
                parsed = parsed.model_copy(update={"work_arrangement": WorkArrangement(persisted.work_arrangement)})
            except ValueError:
                pass
        stored_requirements = self.job_repo.replace_requirements(persisted.id, parsed.requirements)
        parsed = parsed.model_copy(update={"requirements": stored_requirements})
        return JobIngestResponse(job_id=persisted.id, created=created, content_hash=content_hash, parsed=parsed)


class JobMatchService:
    def __init__(
        self,
        *,
        job_repo: JobRepository,
        policy_repo: PolicyRepository,
        career_repo: CareerRepository,
        evidence_search: EvidenceSearchService,
    ) -> None:
        self.job_repo = job_repo
        self.policy_repo = policy_repo
        self.career_repo = career_repo
        self.evidence_search = evidence_search

    def analyze(self, job_id: UUID, request: JobMatchRequest) -> JobMatchResponse:
        job = self.job_repo.get(job_id)
        if job is None:
            raise LookupError("job not found")

        policy = self.policy_repo.get(request.policy_id) if request.policy_id else self.policy_repo.get_active()
        if policy is None:
            raise LookupError("targeting policy not found; create or activate a policy first")

        parser = DeterministicJobParser(self.career_repo.list_skills())
        parsed = parser.parse(job.title, job.description_raw, job.location)
        if job.work_arrangement:
            try:
                parsed = parsed.model_copy(update={"work_arrangement": WorkArrangement(job.work_arrangement)})
            except ValueError:
                pass
        # Always refresh persisted requirements from the current deterministic parser.
        # This is what lets a parser-quality release repair already-ingested jobs.
        requirements = self.job_repo.replace_requirements(job.id, parsed.requirements)

        hard_passed, hard_reasons, location_compensation = self._hard_filters(job, policy, parsed)

        matches: list[_RequirementMatch] = []
        gaps: list[str] = []
        unknowns: list[str] = []
        matched_ordinals: set[int] = set()
        stable_evidence_keys: list[str] = []
        evidence_uuids: list[UUID] = []

        for requirement in requirements:
            result = self._match_requirement(requirement, request)
            matches.append(result)
            coverage = result.coverage
            if coverage.matched:
                matched_ordinals.add(requirement.ordinal)
            elif requirement.importance is RequirementImportance.REQUIRED:
                if coverage.recognized:
                    gaps.append(requirement.text)
                else:
                    unknowns.append(requirement.text)

            for key in coverage.evidence_keys:
                if key not in stable_evidence_keys:
                    stable_evidence_keys.append(key)
            for evidence_id in result.evidence_uuids:
                if evidence_id not in evidence_uuids:
                    evidence_uuids.append(evidence_id)

        set_matches = getattr(self.job_repo, "set_requirement_matches", None)
        if callable(set_matches):
            set_matches(job.id, matched_ordinals)

        coverage_items = [match.coverage for match in matches]
        confidence = self._confidence(coverage_items)
        requirement_score = self._requirements_score(coverage_items)
        title_score = self._title_score(job.title, policy.target_titles)
        seniority_score = self._seniority_score(parsed.seniority, policy.target_seniority)
        role_score = self._role_family_score(parsed.role_family, job.title, policy.target_titles)

        weights = self._normalized_weights(policy)
        components = {
            "requirements": requirement_score,
            "title": title_score,
            "seniority": seniority_score,
            "role_family": role_score,
        }
        base_total = sum(components[name] * weights[name] for name in components)
        # Unknown required items are uncertainty, not automatic failures. They lower the
        # confidence of the score without being treated as a definite mismatch.
        confidence_factor = 0.85 + 0.15 * (confidence.overall_confidence / 100.0)
        total = round(base_total * confidence_factor, 2)

        score_components = [
            ScoreComponent(
                criterion=name,
                weight=weights[name],
                raw_score=score / 100.0,
                weighted_score=(score / 100.0) * weights[name],
                rationale=self._component_rationale(name, score),
                evidence_ids=evidence_uuids if name == "requirements" else [],
            )
            for name, score in components.items()
        ]
        analysis = JobAnalysis(
            job_id=job.id,
            policy_id=policy.id,
            hard_filter_passed=hard_passed,
            hard_filter_reasons=hard_reasons,
            total_score=total,
            components=score_components,
            matched_evidence_ids=evidence_uuids,
            gaps=gaps,
            unknowns=unknowns,
        )
        save = getattr(self.job_repo, "save_analysis")
        try:
            save(
                analysis,
                stable_evidence_keys=stable_evidence_keys,
                requirement_coverage=coverage_items,
                role_family=parsed.role_family,
                seniority=parsed.seniority,
                location_context=location_compensation.model_dump(mode="json"),
                confidence_context=confidence.model_dump(mode="json"),
            )
        except TypeError:
            save(analysis)

        return JobMatchResponse(
            analysis_id=analysis.id,
            job_id=job.id,
            policy_id=policy.id,
            hard_filter_passed=hard_passed,
            hard_filter_reasons=hard_reasons,
            total_score=total,
            role_family=parsed.role_family,
            seniority=parsed.seniority,
            requirement_coverage=coverage_items,
            matched_evidence_keys=stable_evidence_keys,
            gaps=gaps,
            unknowns=unknowns,
            components=components,
            confidence=confidence,
            location_compensation=location_compensation,
        )

    def _match_requirement(self, requirement: ParsedJobRequirement, request: JobMatchRequest) -> _RequirementMatch:
        if requirement.requirement_kind in {RequirementKind.EXPERIENCE_YEARS, RequirementKind.LEADERSHIP_YEARS}:
            tenure = self._match_tenure_requirement(requirement, request)
            if tenure is not None:
                return tenure

        if not requirement.canonical_skills:
            return _RequirementMatch(
                coverage=RequirementCoverage(
                    ordinal=requirement.ordinal,
                    requirement=requirement.text,
                    importance=requirement.importance,
                    requirement_kind=requirement.requirement_kind,
                    skill_match_mode=requirement.skill_match_mode,
                    canonical_skills=[],
                    recognized=False,
                    matched=False,
                    evidence_keys=[],
                    score=0,
                    rationale="No deterministic requirement mapping was available; retained for manual review.",
                ),
                evidence_uuids=(),
            )

        matched_skills = 0
        keys: list[str] = []
        ids: list[UUID] = []
        missing: list[str] = []
        for skill in requirement.canonical_skills:
            response = self._search_skill(skill, request, limit=request.max_evidence_per_requirement)
            if response.results:
                matched_skills += 1
                for item in response.results:
                    if item.evidence_key and item.evidence_key not in keys:
                        keys.append(item.evidence_key)
                    if item.evidence_id not in ids:
                        ids.append(item.evidence_id)
            else:
                missing.append(skill)

        if requirement.skill_match_mode is RequirementSkillMode.ANY:
            matched = matched_skills > 0
            ratio = 1.0 if matched else 0.0
        else:
            ratio = matched_skills / len(requirement.canonical_skills)
            matched = ratio == 1.0

        if matched:
            if requirement.skill_match_mode is RequirementSkillMode.ANY and len(requirement.canonical_skills) > 1:
                rationale = "At least one allowed alternative is supported by verified evidence."
            else:
                rationale = "All recognized skills in this requirement are supported by verified evidence."
        elif matched_skills:
            rationale = "Partial evidence coverage; missing verified evidence for: " + ", ".join(missing)
        else:
            rationale = "No verified evidence was found for the recognized requirement concepts."

        return _RequirementMatch(
            coverage=RequirementCoverage(
                ordinal=requirement.ordinal,
                requirement=requirement.text,
                importance=requirement.importance,
                requirement_kind=requirement.requirement_kind,
                skill_match_mode=requirement.skill_match_mode,
                canonical_skills=requirement.canonical_skills,
                recognized=True,
                matched=matched,
                evidence_keys=keys[: request.max_evidence_per_requirement * max(len(requirement.canonical_skills), 1)],
                score=round(ratio * 100, 2),
                rationale=rationale,
            ),
            evidence_uuids=tuple(ids),
        )

    def _match_tenure_requirement(
        self, requirement: ParsedJobRequirement, request: JobMatchRequest
    ) -> _RequirementMatch | None:
        minimum = requirement.minimum_years
        if minimum is None:
            return None

        lower = requirement.text.lower()
        if requirement.requirement_kind is RequirementKind.LEADERSHIP_YEARS:
            security_ids, sec_keys, sec_uuids = self._experience_ids_for_skills(_SECURITY_TENURE_SKILLS, request)
            leader_ids, lead_keys, lead_uuids = self._experience_ids_for_skills(_LEADERSHIP_SKILLS, request)
            qualifying_ids = security_ids.intersection(leader_ids)
            keys = list(dict.fromkeys(sec_keys + lead_keys))
            ids = list(dict.fromkeys(sec_uuids + lead_uuids))
            label = "verified security-leadership experience"
        elif "security" in lower or "security engineering" in lower:
            qualifying_ids, keys, ids = self._experience_ids_for_skills(_SECURITY_TENURE_SKILLS, request)
            label = "verified security-engineering experience"
        elif requirement.canonical_skills:
            qualifying_ids, keys, ids = self._experience_ids_for_skills(tuple(requirement.canonical_skills), request)
            label = "verified relevant experience"
        else:
            return None

        years = self._union_years(qualifying_ids)
        ratio = min(years / minimum, 1.0) if minimum else 1.0
        matched = years >= minimum

        # The role-span calculation is useful as an internal threshold test, but
        # it is not precise enough to claim a decimal number of specialized
        # security years. A role can contain qualifying security work without
        # every day of that role being exclusively security engineering or
        # leadership. Persist a threshold proof plus the qualifying experiences
        # instead of exposing pseudo-precision.
        if matched:
            rationale = (
                f"Verified qualifying career evidence meets the {minimum}+ year {label} threshold; "
                "exact specialized tenure is intentionally not asserted."
            )
        else:
            rationale = (
                f"Verified qualifying career evidence does not establish the {minimum}+ year {label} threshold; "
                "manual review is recommended."
            )

        experience_keys = self._canonical_experience_keys(qualifying_ids)
        return _RequirementMatch(
            coverage=RequirementCoverage(
                ordinal=requirement.ordinal,
                requirement=requirement.text,
                importance=requirement.importance,
                requirement_kind=requirement.requirement_kind,
                skill_match_mode=requirement.skill_match_mode,
                canonical_skills=requirement.canonical_skills,
                recognized=True,
                matched=matched,
                evidence_keys=keys[: request.max_evidence_per_requirement * 2],
                score=round(ratio * 100, 2),
                rationale=rationale,
                minimum_years=minimum,
                tenure_threshold_met=matched,
                qualifying_experience_keys=experience_keys,
            ),
            evidence_uuids=tuple(ids),
        )

    def _experience_ids_for_skills(
        self, skills: tuple[str, ...], request: JobMatchRequest
    ) -> tuple[set[UUID], list[str], list[UUID]]:
        experience_ids: set[UUID] = set()
        keys: list[str] = []
        ids: list[UUID] = []
        for skill in skills:
            response = self._search_skill(skill, request, limit=100)
            for item in response.results:
                if item.experience_id:
                    experience_ids.add(item.experience_id)
                if item.evidence_key and item.evidence_key not in keys:
                    keys.append(item.evidence_key)
                if item.evidence_id not in ids:
                    ids.append(item.evidence_id)
        return experience_ids, keys, ids

    def _canonical_experience_keys(self, experience_ids: set[UUID]) -> list[str]:
        if not experience_ids:
            return []
        keys: list[str] = []
        for experience in self.career_repo.list_experiences():
            if experience.id not in experience_ids:
                continue
            key = getattr(experience, "canonical_key", None)
            if key and key not in keys:
                keys.append(key)
        return keys

    def _search_skill(self, skill: str, request: JobMatchRequest, *, limit: int):
        search = EvidenceSearchRequest(
            skills=[skill],
            scope=RetrievalScope.RESUME if request.resume_safe_only else RetrievalScope.GENERAL,
            match_mode=MatchMode.ALL,
            verification_statuses=[VerificationStatus.USER_VERIFIED],
            approval_statuses=[ApprovalStatus.APPROVED],
            limit=limit,
        )
        return self.evidence_search.search(search)

    def _union_years(self, experience_ids: set[UUID]) -> float:
        if not experience_ids:
            return 0.0
        intervals: list[tuple[date, date]] = []
        today = date.today()
        for experience in self.career_repo.list_experiences():
            if experience.id not in experience_ids:
                continue
            end = experience.end_date or today
            if end >= experience.start_date:
                intervals.append((experience.start_date, end))
        if not intervals:
            return 0.0
        intervals.sort()
        merged: list[tuple[date, date]] = [intervals[0]]
        for start, end in intervals[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end + timedelta(days=1):
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        days = sum((end - start).days + 1 for start, end in merged)
        return days / 365.25

    @staticmethod
    def _requirements_score(coverage: list[RequirementCoverage]) -> float:
        scored = [
            item for item in coverage
            if item.importance in {RequirementImportance.REQUIRED, RequirementImportance.PREFERRED}
        ]
        if not scored:
            return 0.0
        numerator = 0.0
        denominator = 0.0
        for item in scored:
            weight = _REQUIREMENT_WEIGHTS[item.importance]
            # Unknowns are uncertainty, not evidence of failure. Give them a neutral
            # 50 score while confidence separately records that the requirement was not resolved.
            effective_score = item.score if item.recognized else 50.0
            numerator += (effective_score / 100.0) * weight
            denominator += weight
        return round((numerator / denominator) * 100, 2) if denominator else 0.0

    @staticmethod
    def _confidence(coverage: list[RequirementCoverage]) -> MatchConfidence:
        required = [item for item in coverage if item.importance is RequirementImportance.REQUIRED]
        preferred = [item for item in coverage if item.importance is RequirementImportance.PREFERRED]
        req_rec = [item for item in required if item.recognized]
        pref_rec = [item for item in preferred if item.recognized]
        req_match = [item for item in required if item.matched]
        pref_match = [item for item in preferred if item.matched]

        req_rec_pct = 100.0 if not required else 100.0 * len(req_rec) / len(required)
        req_match_pct = 0.0 if not required else 100.0 * len(req_match) / len(required)
        pref_rec_pct = 100.0 if not preferred else 100.0 * len(pref_rec) / len(preferred)
        pref_match_pct = 0.0 if not preferred else 100.0 * len(pref_match) / len(preferred)
        if preferred:
            overall = 0.8 * req_rec_pct + 0.2 * pref_rec_pct
        else:
            overall = req_rec_pct
        return MatchConfidence(
            required_total=len(required),
            required_recognized=len(req_rec),
            required_matched=len(req_match),
            required_unknown=len(required) - len(req_rec),
            preferred_total=len(preferred),
            preferred_recognized=len(pref_rec),
            preferred_matched=len(pref_match),
            recognized_required_pct=round(req_rec_pct, 2),
            matched_required_pct=round(req_match_pct, 2),
            matched_preferred_pct=round(pref_match_pct, 2),
            overall_confidence=round(overall, 2),
            manual_review_required=len(req_rec) < len(required),
        )

    @staticmethod
    def _title_score(title: str, targets: list[str]) -> float:
        if not targets:
            return 100.0
        title_tokens = set(normalize_term(title).split())
        best = 0.0
        for target in targets:
            target_tokens = set(normalize_term(target).split())
            if not target_tokens:
                continue
            overlap = len(title_tokens & target_tokens) / len(target_tokens)
            best = max(best, overlap)
        return round(best * 100, 2)

    @staticmethod
    def _seniority_score(seniority: str | None, targets: list[str]) -> float:
        if not targets:
            return 100.0
        normalized_targets = {normalize_term(value) for value in targets}
        if seniority is None:
            return 50.0
        return 100.0 if normalize_term(seniority) in normalized_targets else 0.0

    @staticmethod
    def _role_family_score(role_family: str, title: str, targets: list[str]) -> float:
        if not targets:
            return 100.0
        family_terms = {
            "application_security": {"application security", "appsec", "product security"},
            "security_architecture": {"security architect", "security architecture"},
            "cloud_security": {"cloud security", "infrastructure security"},
            "ai_security": {"ai security", "ai ml security", "llm security"},
            "security_engineering": {"security engineer", "security engineering", "head of security engineering"},
            "security_leadership": {"security director", "director of security", "head of security"},
        }.get(role_family, set())
        normalized_targets = [normalize_term(value) for value in targets]
        if any(any(term in target for term in family_terms) for target in normalized_targets):
            return 100.0
        title_norm = normalize_term(title)
        return 75.0 if any(term in title_norm for term in family_terms) else 25.0

    def _hard_filters(
        self, job: JobOpportunity, policy: TargetingPolicy, parsed: ParsedJobDescription
    ) -> tuple[bool, list[str], LocationCompensationDecision]:
        base = evaluate_hard_filters(job, policy)
        reasons = list(base.reasons)

        if parsed.work_arrangement is WorkArrangement.REMOTE and not policy.remote_allowed:
            reasons.append("Remote work is disallowed by the targeting policy")
        elif parsed.work_arrangement is WorkArrangement.HYBRID and not policy.hybrid_allowed:
            reasons.append("Hybrid work is disallowed by the targeting policy")
        elif parsed.work_arrangement is WorkArrangement.ONSITE and not policy.onsite_allowed:
            reasons.append("Onsite work is disallowed by the targeting policy")

        if policy.allowed_locations and job.location:
            location = normalize_term(job.location)
            if not any(normalize_term(allowed) in location for allowed in policy.allowed_locations):
                reasons.append(f"Location not allowed by policy: {job.location}")

        location_result = evaluate_location_compensation(job, policy, parsed.work_arrangement)
        if location_result.hard_filter_reason:
            reasons.append(location_result.hard_filter_reason)

        return (not reasons), reasons, location_result.decision

    @staticmethod
    def _normalized_weights(policy: TargetingPolicy) -> dict[str, float]:
        raw = dict(_DEFAULT_WEIGHTS)
        for key in raw:
            if key in policy.weights:
                raw[key] = max(float(policy.weights[key]), 0.0)
        total = sum(raw.values()) or 1.0
        return {key: value / total for key, value in raw.items()}

    @staticmethod
    def _component_rationale(name: str, score: float) -> str:
        labels = {
            "requirements": "Weighted required/preferred coverage, with unresolved requirements treated as uncertainty",
            "title": "Token overlap between the job title and configured target titles",
            "seniority": "Detected seniority compared with configured target seniority",
            "role_family": "Detected security role family compared with configured target titles",
        }
        return f"{labels[name]}: {score:.2f}/100"
