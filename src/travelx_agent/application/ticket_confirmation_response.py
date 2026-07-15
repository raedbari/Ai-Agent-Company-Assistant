from travelx_agent.application.ticket_creation_service import TicketConfirmationResult
from travelx_agent.application.response_builder import (
    department_label,
    ticket_status_label,
)
from travelx_agent.domain.assistant_response import AssistantResponse
from travelx_agent.domain.policy_decision import PolicyAction
from travelx_agent.domain.ticket import TicketConfirmationOutcome


def build_ticket_confirmation_response(
    result: TicketConfirmationResult,
) -> AssistantResponse:
    conversation = result.conversation
    draft = conversation.ticket_draft

    if result.outcome is TicketConfirmationOutcome.CREATED and result.ticket:
        text = (
            f"تم إنشاء التذكرة بنجاح. رقم التذكرة: {result.ticket.ticket_number}. "
            f"الحالة: {ticket_status_label(result.ticket.status)}. "
            f"القسم المسؤول: {department_label(result.ticket.assigned_department)}."
        )
    elif result.outcome is TicketConfirmationOutcome.ALREADY_CREATED and result.ticket:
        text = (
            "هذه التذكرة منشأة مسبقًا، ولم ننشئ نسخة مكررة. "
            f"رقم التذكرة: {result.ticket.ticket_number}."
        )
    elif result.outcome is TicketConfirmationOutcome.VERSION_REQUIRED:
        text = (
            "يجب تأكيد إصدار محدد من المسودة. "
            f"الإصدار الحالي هو {result.expected_version}."
        )
    elif result.outcome is TicketConfirmationOutcome.VERSION_CONFLICT:
        text = (
            "لم تُنشأ التذكرة لأن المسودة تغيرت بعد الإصدار الذي حاولت تأكيده. "
            f"راجع وأكد الإصدار {result.expected_version}."
        )
    else:
        text = "لا يمكن إنشاء التذكرة قبل اكتمال المتطلبات وتجهيز المسودة."

    conversation.last_assistant_response = text
    return AssistantResponse(
        text=text,
        policy_action=PolicyAction.CONTINUE,
        stage=conversation.stage,
        service_key=draft.service_key if draft else None,
        primary_department=draft.primary_department if draft else None,
        missing_requirements=conversation.missing_requirements,
    )