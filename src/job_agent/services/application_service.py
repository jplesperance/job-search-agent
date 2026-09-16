from datetime import datetime, timezone

from job_agent.domain.models import Application, ApplicationEvent
from job_agent.domain.state_machine import ensure_transition_allowed
from job_agent.domain.enums import ApplicationStatus


def transition_application(
    application: Application,
    target: ApplicationStatus,
    *,
    actor: str,
    detail: dict[str, object] | None = None,
) -> ApplicationEvent:
    ensure_transition_allowed(application.status, target)
    previous = application.status
    application.status = target
    application.updated_at = datetime.now(timezone.utc)

    return ApplicationEvent(
        application_id=application.id,
        event_type="application.status_changed",
        from_status=previous,
        to_status=target,
        actor=actor,
        detail=detail or {},
    )
