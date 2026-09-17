from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from job_agent.domain.enums import ApprovalStatus, VerificationStatus
from job_agent.domain.jobs import (
    JobIngestRequest,
    JobIngestResponse,
    JobMatchRequest,
    JobMatchResponse,
    LocationCompensationDecision,
    ParsedJobDescription,
    ParsedJobRequirement,
    RequirementCoverage,
    RequirementImportance,
    WorkArrangement,
)
from job_agent.domain.models import JobAnalysis, JobOpportunity, ScoreComponent, TargetingPolicy
from job_agent.domain.retrieval import EvidenceSearchRequest, MatchMode, RetrievalScope, normalize_term
from job_agent.repositories.interfaces import CareerRepository, JobRepository, PolicyRepository
from job_agent.scoring.hard_filters import evaluate_hard_filters
from job_agent.services.evidence_search import EvidenceSearchService
from job_agent.services.job_parser import DeterministicJobParser
from job_agent.services.location_policy import evaluate_location_compensation


_DEFAULT_WEIGHTS = {
    "requirements": 0.60,
    "title": 0.15,
    "seniority": 0.10,
    "role_family": 0.15,
}

_REQUIREMENT_WEIGHTS = {
    RequirementImportance.REQUIRED: 3.0,
    RequirementImportance.PREFERRED: 1.5,
    RequirementImportance.CONTEXT: 1.0,
}


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
        job = JobOpportunity(
            source=request.source,
            external_id=request.external_id,
            source_url=request.source_url,
            company=request.company.strip(),
            title=request.title.strip(),
            location=request.location.strip() if request.location else None,
            compensation_text=request.compensation_text,
            description_raw=request.description_raw,
        )
        persisted, created = self.job_repo.upsert(job, content_hash)
        parser = DeterministicJobParser(self.career_repo.list_skills())
        parsed = parser.parse(persisted.title, persisted.description_raw, persisted.location)
        stored_requirements = self.job_repo.replace_requirements(persisted.id, parsed.requirements)
        parsed = parsed.model_copy(update={"requirements": stored_requirements})
        return JobIngestResponse(
            job_id=persisted.id,
            created=created,
            content_hash=content_hash,
            parsed=parsed,
        )


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
        requirements = self.job_repo.list_requirements(job.id)
        if not requirements:
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
            if result.coverage.matched:
                matched_ordinals.add(requirement.ordinal)
            elif requirement.canonical_skills and requirement.importance is RequirementImportance.REQUIRED:
                gaps.append(requirement.text)
            elif not requirement.canonical_skills and requirement.importance is RequirementImportance.REQUIRED:
                unknowns.append(requirement.text)

            for key in result.coverage.evidence_keys:
                if key not in stable_evidence_keys:
                    stable_evidence_keys.append(key)
            for evidence_id in result.evidence_uuids:
                if evidence_id not in evidence_uuids:
                    evidence_uuids.append(evidence_id)

        # Optional repository extension used by SQL implementation.
        set_matches = getattr(self.job_repo, "set_requirement_matches", None)
        if callable(set_matches):
            set_matches(job.id, matched_ordinals)

        requirement_score = self._requirements_score([match.coverage for match in matches])
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
        total = round(sum(components[name] * weights[name] for name in components), 2)

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
                requirement_coverage=[match.coverage for match in matches],
                role_family=parsed.role_family,
                seniority=parsed.seniority,
                location_context=location_compensation.model_dump(mode="json"),
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
            requirement_coverage=[match.coverage for match in matches],
            matched_evidence_keys=stable_evidence_keys,
            gaps=gaps,
            unknowns=unknowns,
            components=components,
            location_compensation=location_compensation,
        )

    def _match_requirement(
        self, requirement: ParsedJobRequirement, request: JobMatchRequest
    ) -> _RequirementMatch:
        if not requirement.canonical_skills:
            return _RequirementMatch(
                coverage=RequirementCoverage(
                    ordinal=requirement.ordinal,
                    requirement=requirement.text,
                    importance=requirement.importance,
                    canonical_skills=[],
                    matched=False,
                    evidence_keys=[],
                    score=0,
                    rationale="No canonical career-taxonomy skill was detected; retained as an unknown requirement.",
                ),
                evidence_uuids=(),
            )

        matched_skills = 0
        keys: list[str] = []
        ids: list[UUID] = []
        missing: list[str] = []
        for skill in requirement.canonical_skills:
            search = EvidenceSearchRequest(
                skills=[skill],
                scope=RetrievalScope.RESUME if request.resume_safe_only else RetrievalScope.GENERAL,
                match_mode=MatchMode.ALL,
                verification_statuses=[VerificationStatus.USER_VERIFIED],
                approval_statuses=[ApprovalStatus.APPROVED],
                limit=request.max_evidence_per_requirement,
            )
            response = self.evidence_search.search(search)
            if response.results:
                matched_skills += 1
                for item in response.results:
                    if item.evidence_key and item.evidence_key not in keys:
                        keys.append(item.evidence_key)
                    if item.evidence_id not in ids:
                        ids.append(item.evidence_id)
            else:
                missing.append(skill)

        ratio = matched_skills / len(requirement.canonical_skills)
        matched = ratio == 1.0
        if matched:
            rationale = "All recognized skills in this requirement are supported by verified evidence."
        elif matched_skills:
            rationale = "Partial evidence coverage; missing verified evidence for: " + ", ".join(missing)
        else:
            rationale = "No verified evidence was found for the recognized skills in this requirement."

        return _RequirementMatch(
            coverage=RequirementCoverage(
                ordinal=requirement.ordinal,
                requirement=requirement.text,
                importance=requirement.importance,
                canonical_skills=requirement.canonical_skills,
                matched=matched,
                evidence_keys=keys[: request.max_evidence_per_requirement * len(requirement.canonical_skills)],
                score=round(ratio * 100, 2),
                rationale=rationale,
            ),
            evidence_uuids=tuple(ids),
        )

    @staticmethod
    def _requirements_score(coverage: list[RequirementCoverage]) -> float:
        scored = [item for item in coverage if item.canonical_skills]
        if not scored:
            return 0.0
        numerator = 0.0
        denominator = 0.0
        for item in scored:
            weight = _REQUIREMENT_WEIGHTS[item.importance]
            numerator += (item.score / 100.0) * weight
            denominator += weight
        return round((numerator / denominator) * 100, 2) if denominator else 0.0

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
            "ai_security": {"ai security", "llm security"},
            "security_engineering": {"security engineer", "security engineering"},
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
            "requirements": "Weighted coverage of recognized job requirements by verified career evidence",
            "title": "Token overlap between the job title and configured target titles",
            "seniority": "Detected seniority compared with configured target seniority",
            "role_family": "Detected security role family compared with configured target titles",
        }
        return f"{labels[name]}: {score:.2f}/100"
