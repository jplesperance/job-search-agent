from job_agent.domain.enums import ApplicationStatus


TERMINAL_STATUSES = {
    ApplicationStatus.OFFER,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
    ApplicationStatus.POSITION_CLOSED,
    ApplicationStatus.NO_RESPONSE,
}

ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.DISCOVERED: {
        ApplicationStatus.QUALIFIED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.POSITION_CLOSED,
    },
    ApplicationStatus.QUALIFIED: {
        ApplicationStatus.RESUME_GENERATED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.POSITION_CLOSED,
    },
    ApplicationStatus.RESUME_GENERATED: {
        ApplicationStatus.AWAITING_APPROVAL,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.AWAITING_APPROVAL: {
        ApplicationStatus.APPLIED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.APPLIED: {
        ApplicationStatus.RECRUITER_CONTACT,
        ApplicationStatus.REJECTED,
        ApplicationStatus.NO_RESPONSE,
        ApplicationStatus.POSITION_CLOSED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.RECRUITER_CONTACT: {
        ApplicationStatus.PHONE_SCREEN,
        ApplicationStatus.INTERVIEWING,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.PHONE_SCREEN: {
        ApplicationStatus.INTERVIEWING,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.INTERVIEWING: {
        ApplicationStatus.FINAL_INTERVIEW,
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.FINAL_INTERVIEW: {
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
}


class InvalidStatusTransition(ValueError):
    pass


def ensure_transition_allowed(current: ApplicationStatus, target: ApplicationStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidStatusTransition(f"Invalid application transition: {current} -> {target}")
