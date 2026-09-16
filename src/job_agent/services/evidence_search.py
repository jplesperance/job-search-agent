from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from job_agent.domain.enums import ResumeVisibility
from job_agent.domain.retrieval import (
    EvidenceRecord,
    EvidenceSearchRequest,
    EvidenceSearchResponse,
    EvidenceSearchResult,
    MatchMode,
    RetrievalScope,
    normalize_term,
)
from job_agent.repositories.interfaces import CareerRepository, EvidenceRepository


@dataclass(frozen=True)
class _ResolvedSkill:
    requested: str
    canonical_names: frozenset[str]


class EvidenceSearchService:
    def __init__(self, evidence_repo: EvidenceRepository, career_repo: CareerRepository) -> None:
        self.evidence_repo = evidence_repo
        self.career_repo = career_repo

    def search(self, request: EvidenceSearchRequest) -> EvidenceSearchResponse:
        resolved, unknown = self._resolve_skills(request.skills)

        resume_eligible = request.resume_eligible
        resume_visibility = request.resume_visibility
        if request.scope is RetrievalScope.RESUME:
            resume_eligible = True
            resume_visibility = [ResumeVisibility.PUBLIC_SAFE, ResumeVisibility.GENERALIZE]

        records = self.evidence_repo.list_records(
            experience_ids=request.experience_ids or None,
            categories=request.categories or None,
            verification_statuses=request.verification_statuses or None,
            approval_statuses=request.approval_statuses or None,
            resume_eligible=resume_eligible,
            resume_visibility=resume_visibility or None,
        )

        scored: list[EvidenceSearchResult] = []
        for record in records:
            result = self._score_record(record, request, resolved)
            if result is not None:
                scored.append(result)

        scored.sort(
            key=lambda item: (
                -item.score,
                item.employer or "",
                item.evidence_key or str(item.evidence_id),
            )
        )
        results = scored[: request.limit]

        return EvidenceSearchResponse(
            query=request.query,
            requested_skills=request.skills,
            resolved_skills={item.requested: sorted(item.canonical_names) for item in resolved},
            unknown_skills=unknown,
            count=len(results),
            results=results,
        )

    def _resolve_skills(self, requested_skills: list[str]) -> tuple[list[_ResolvedSkill], list[str]]:
        taxonomy = self.career_repo.list_skills()
        lookup: dict[str, set[str]] = defaultdict(set)
        for skill in taxonomy:
            lookup[normalize_term(skill.name)].add(skill.name)
            for alias in skill.aliases:
                lookup[normalize_term(alias)].add(skill.name)

        resolved: list[_ResolvedSkill] = []
        unknown: list[str] = []
        for requested in requested_skills:
            canonical_names = lookup.get(normalize_term(requested), set())
            if canonical_names:
                resolved.append(
                    _ResolvedSkill(requested=requested, canonical_names=frozenset(canonical_names))
                )
            else:
                unknown.append(requested)
        return resolved, unknown

    def _score_record(
        self,
        record: EvidenceRecord,
        request: EvidenceSearchRequest,
        resolved: list[_ResolvedSkill],
    ) -> EvidenceSearchResult | None:
        skill_names = {skill.name for skill in record.skills}
        matched_requested: list[str] = []
        matched_canonical: set[str] = set()
        for item in resolved:
            overlap = skill_names.intersection(item.canonical_names)
            if overlap:
                matched_requested.append(item.requested)
                matched_canonical.update(overlap)

        if request.skills:
            # An unknown requested skill cannot satisfy ALL semantics.
            if request.match_mode is MatchMode.ALL:
                if len(resolved) != len(request.skills) or len(matched_requested) != len(request.skills):
                    return None
            elif not matched_requested and not (request.query and request.query.strip()):
                return None

        query_tokens = self._query_tokens(request.query)
        haystack = self._haystack(record)
        matched_query_tokens = [token for token in query_tokens if token in haystack]

        if query_tokens and not matched_query_tokens and not matched_requested:
            return None

        score, reasons = self._calculate_score(
            request=request,
            matched_skill_count=len(matched_requested),
            resolved_skill_count=len(resolved),
            query_token_count=len(query_tokens),
            matched_query_count=len(matched_query_tokens),
            haystack=haystack,
        )

        evidence = record.evidence
        experience = record.experience
        safe_for_resume = bool(
            evidence.resume_eligible
            and evidence.resume_visibility
            in {ResumeVisibility.PUBLIC_SAFE, ResumeVisibility.GENERALIZE}
        )

        return EvidenceSearchResult(
            evidence_id=evidence.id,
            evidence_key=evidence.evidence_key,
            claim=evidence.claim,
            category=evidence.category,
            context=evidence.context,
            metric=evidence.metric,
            verification_status=evidence.verification_status,
            approval_status=evidence.approval_status,
            resume_eligible=evidence.resume_eligible,
            resume_visibility=evidence.resume_visibility,
            safe_for_resume=safe_for_resume,
            tags=sorted(evidence.tags),
            experience_id=evidence.experience_id,
            experience_key=experience.canonical_key if experience else None,
            employer=experience.employer if experience else None,
            title=experience.title if experience else None,
            matched_skills=sorted(matched_canonical),
            all_skills=sorted(skill_names),
            score=score,
            score_reasons=reasons,
        )

    @staticmethod
    def _query_tokens(query: str | None) -> list[str]:
        if not query:
            return []
        normalized = normalize_term(query)
        return [token for token in normalized.split() if len(token) >= 3]

    @staticmethod
    def _haystack(record: EvidenceRecord) -> str:
        evidence = record.evidence
        experience = record.experience
        values = [
            evidence.claim,
            evidence.context or "",
            evidence.metric or "",
            evidence.category,
            " ".join(evidence.tags),
            " ".join(skill.name for skill in record.skills),
            experience.employer if experience else "",
            experience.title if experience else "",
        ]
        return normalize_term(" ".join(values))

    @staticmethod
    def _calculate_score(
        *,
        request: EvidenceSearchRequest,
        matched_skill_count: int,
        resolved_skill_count: int,
        query_token_count: int,
        matched_query_count: int,
        haystack: str,
    ) -> tuple[float, list[str]]:
        reasons: list[str] = []
        has_skills = bool(request.skills)
        has_query = bool(query_token_count)

        skill_ratio = matched_skill_count / max(len(request.skills), 1) if has_skills else 0.0
        query_ratio = matched_query_count / max(query_token_count, 1) if has_query else 0.0

        if has_skills and has_query:
            score = 70.0 * skill_ratio + 30.0 * query_ratio
        elif has_skills:
            score = 100.0 * skill_ratio
        else:
            score = 100.0 * query_ratio

        if matched_skill_count:
            reasons.append(
                f"matched {matched_skill_count}/{len(request.skills)} requested skill terms"
            )
        elif has_skills and not resolved_skill_count:
            reasons.append("none of the requested skill terms resolved to the taxonomy")

        if matched_query_count:
            reasons.append(f"matched {matched_query_count}/{query_token_count} query terms")

        if request.query:
            normalized_query = normalize_term(request.query)
            if normalized_query and normalized_query in haystack:
                score = min(100.0, score + 5.0)
                reasons.append("matched the normalized query phrase")

        return round(min(100.0, score), 2), reasons
