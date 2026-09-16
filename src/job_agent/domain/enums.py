from enum import StrEnum


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"


class VerificationStatus(StrEnum):
    SOURCE_FACT = "SOURCE_FACT"
    CORROBORATED = "CORROBORATED"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    USER_VERIFIED = "USER_VERIFIED"


class ResumeVisibility(StrEnum):
    PUBLIC_SAFE = "public_safe"
    GENERALIZE = "generalize"
    INTERNAL_ONLY = "internal_only"


class ApplicationStatus(StrEnum):
    DISCOVERED = "discovered"
    QUALIFIED = "qualified"
    RESUME_GENERATED = "resume_generated"
    AWAITING_APPROVAL = "awaiting_approval"
    APPLIED = "applied"
    RECRUITER_CONTACT = "recruiter_contact"
    PHONE_SCREEN = "phone_screen"
    INTERVIEWING = "interviewing"
    FINAL_INTERVIEW = "final_interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    POSITION_CLOSED = "position_closed"
    NO_RESPONSE = "no_response"
