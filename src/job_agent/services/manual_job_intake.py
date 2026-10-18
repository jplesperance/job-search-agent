"""Submit pasted or fetched job descriptions through the existing matching pipeline."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from job_agent.db.tables import DiscoverySourceRow, NotificationStateRow
from job_agent.domain.jobs import JobIngestRequest, JobMatchRequest, WorkArrangement
from job_agent.domain.manual_intake import ManualJobIntakeRequest, ManualJobIntakeResponse
from job_agent.services.canonical_jobs import normalize_source_url
from job_agent.services.job_matching import JobIngestionService, JobMatchService
from job_agent.services.manual_job_fetch import FetchedJob, ManualFetchError, retrieve_job


class ManualJobIntakeService:
    def __init__(
        self, *, ingestion: JobIngestionService, matcher: JobMatchService,
        session: Session | None = None, fetcher=retrieve_job,
    ) -> None:
        self.ingestion = ingestion
        self.matcher = matcher
        self.session = session
        self.fetcher = fetcher

    def _suppress_push(self, job_id) -> bool:
        if self.session is None:
            return False
        already = self.session.execute(
            select(NotificationStateRow).where(
                NotificationStateRow.job_id == job_id,
                NotificationStateRow.channel == "pushover",
                NotificationStateRow.notification_type == "new_match",
            )
        ).scalar_one_or_none()
        if already is not None:
            if already.status in {"pending", "failed"}:
                # Manual intent supersedes an unsent scheduled alert.
                already.status = "suppressed"
                already.last_error = None
                self.session.flush()
                return True
            return already.status == "suppressed"
        self.session.add(NotificationStateRow(
            id=uuid4(), job_id=job_id, discovery_run_id=None,
            channel="pushover", notification_type="new_match",
            status="suppressed", attempt_count=0,
            created_at=datetime.now(timezone.utc),
        ))
        self.session.flush()
        return True

    def submit(self, request: ManualJobIntakeRequest) -> ManualJobIntakeResponse:
        provided_url = str(request.source_url) if request.source_url else None
        fetched: FetchedJob | None = None
        # Pasted text is authoritative; no unexpected HTTP request when provided.
        if not (request.description_raw and request.description_raw.strip()) and provided_url:
            fetched = self.fetcher(provided_url)
        description = (request.description_raw or (fetched.description_raw if fetched else "")).strip()
        company = (request.company or (fetched.company if fetched else None) or "").strip()
        if not company and fetched and fetched.ats_provider and fetched.ats_board and self.session is not None:
            # Known board identifiers are authoritative only if they are already
            # configured in the user's discovery source registry.
            matched_source = self.session.execute(
                select(DiscoverySourceRow).where(
                    DiscoverySourceRow.provider == fetched.ats_provider,
                    func.lower(DiscoverySourceRow.board_identifier) == fetched.ats_board.casefold(),
                ).limit(1)
            ).scalar_one_or_none()
            if matched_source is not None:
                company = matched_source.company
        title = (request.title or (fetched.title if fetched else None) or "").strip()
        if not company or not title:
            raise ManualFetchError(
                "Could not determine the company and job title; provide --company and --title "
                "(and --text-file if the description is inaccessible)"
            )
        if len(description) < 80:
            raise ManualFetchError("Complete job description is required (at least 80 characters)")
        url = (fetched.source_url if fetched else provided_url)
        if url:
            normalized = normalize_source_url(url)
            identity = f"url:{normalized}"
            source = "manual:url"
        else:
            identity = f"text:{company.casefold()}:{title.casefold()}:{description}"
            source = "manual:text"
        external_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        location = request.location or (fetched.location if fetched else None)
        arrangement = request.work_arrangement
        if arrangement is None and location and location.casefold() == "remote":
            arrangement = WorkArrangement.REMOTE
        ingest_request = JobIngestRequest(
            source=source, external_id=external_id, source_url=url,
            company=company, title=title, location=location,
            compensation_text=request.compensation_text or (fetched.compensation_text if fetched else None),
            work_arrangement=arrangement, description_raw=description,
        )
        ingested = self.ingestion.ingest(ingest_request)
        # Important: suppress *before* analysis/commit so the scheduled notifier
        # can never race a committed manually supplied candidate.
        suppressed = self._suppress_push(ingested.job_id)
        match = self.matcher.analyze(ingested.job_id, JobMatchRequest())
        return ManualJobIntakeResponse(
            ingestion=ingested, analysis=match,
            extraction_method="pasted_text" if request.description_raw else fetched.extraction_method,
            canonical_duplicate=not ingested.created,
            notification_suppressed=suppressed,
        )
