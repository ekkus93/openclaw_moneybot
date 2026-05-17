"""Safe email templates."""

from __future__ import annotations

from openclaw_moneybot.skills.email_drafter.models import EmailDraftRequest


def _recipient_line(request: EmailDraftRequest) -> str:
    return request.recipient_name or request.recipient_organization or "there"


def _disclosure(request: EmailDraftRequest) -> str:
    if not request.automation_disclosure_required:
        return ""
    return (
        "\n\nThis message was prepared with automation assistance. "
        "A human reviews material commitments."
    )


def render_template(request: EmailDraftRequest) -> tuple[str, str, str]:
    """Render a safe template based on purpose."""
    greeting = f"Hello {_recipient_line(request)},"
    context = request.context_summary.strip()
    call_to_action = request.requested_call_to_action.strip()

    if request.purpose == "bounty_application":
        subject = "Question about the listed bounty"
        source_reference = request.source_url or "the shared listing"
        body = (
            f"{greeting}\n\n"
            "I am reaching out about the opportunity described here: "
            f"{source_reference}.\n"
            f"{context}\n\n"
            f"My specific request is: {call_to_action}.\n"
            f"I will keep any next step within the documented rules and scope."
            f"{_disclosure(request)}"
        )
        return "bounty_application", subject, body

    if request.purpose == "vendor_question":
        subject = "Question about your product or service"
        body = (
            f"{greeting}\n\n"
            "I am evaluating a small, clearly scoped purchase related to this "
            f"context: {context}\n\n"
            f"Could you clarify the following: {call_to_action}?\n"
            f"I am not making a purchase commitment in this message."
            f"{_disclosure(request)}"
        )
        return "vendor_question", subject, body

    if request.purpose == "receipt_request":
        subject = "Receipt request"
        body = (
            f"{greeting}\n\n"
            "I am requesting a receipt or invoice for the following transaction "
            f"context: {context}\n\n"
            f"Requested action: {call_to_action}.\n"
            f"If needed, I can provide the non-sensitive transaction reference already on record."
            f"{_disclosure(request)}"
        )
        return "receipt_request", subject, body

    if request.purpose == "followup":
        subject = "Following up on a previous message"
        body = (
            f"{greeting}\n\n"
            f"I am following up once on the earlier thread regarding: {context}\n\n"
            f"If helpful, the next step would be: {call_to_action}.\n"
            f"If this is not relevant, no response is needed."
            f"{_disclosure(request)}"
        )
        return "followup", subject, body

    subject = "Question"
    body = (
        f"{greeting}\n\n"
        f"{context}\n\n"
        f"Requested next step: {call_to_action}."
        f"{_disclosure(request)}"
    )
    return "generic", subject, body
