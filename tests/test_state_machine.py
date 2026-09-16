import pytest

from job_agent.domain.enums import ApplicationStatus
from job_agent.domain.models import Application
from job_agent.domain.state_machine import InvalidStatusTransition
from job_agent.services.application_service import transition_application


def test_valid_transition_emits_event() -> None:
    app = Application(job_id="00000000-0000-0000-0000-000000000001")

    event = transition_application(app, ApplicationStatus.QUALIFIED, actor="test")

    assert app.status == ApplicationStatus.QUALIFIED
    assert event.from_status == ApplicationStatus.DISCOVERED
    assert event.to_status == ApplicationStatus.QUALIFIED


def test_invalid_transition_is_rejected() -> None:
    app = Application(job_id="00000000-0000-0000-0000-000000000001")

    with pytest.raises(InvalidStatusTransition):
        transition_application(app, ApplicationStatus.OFFER, actor="test")
