import re

from travelx_agent.application.requirements_collector import RequirementCollectionResult
from travelx_agent.domain.assistant_response import AssistantResponse
from travelx_agent.domain.conversation_state import ConversationStage, ConversationState
from travelx_agent.domain.knowledge import KnowledgeSource
from travelx_agent.domain.message_decision import MessageDecision, MessageIntent
from travelx_agent.domain.policy_decision import PolicyAction, PolicyDecision
from travelx_agent.domain.service_catalog import (
    Department,
    RequirementDefinition,
    RequirementValueKind,
    ServiceDefinition,
    ServiceKey,
    get_service,
)
from travelx_agent.domain.ticket import TicketStatus
from travelx_agent.domain.ticket_draft import (
    FeatureDecisionAction,
    TicketDraft,
    TicketEditOperation,
    TicketEditResult,
    TicketFeatureDecision,
)


DEPARTMENT_LABELS: dict[Department, str] = {
    Department.CYBTX: "CYBTX",
    Department.DESTINATION: "Destination",
    Department.TXSAAS: "TXSaaS",
}

TICKET_STATUS_LABELS: dict[TicketStatus, str] = {
    TicketStatus.NEW: "جديدة",
}

_TEXT_SEPARATORS = re.compile(r"[\W_]+", re.UNICODE)
_IDENTITY_QUESTIONS = (
    "مااسمك",
    "منانت",
    "مينانت",
    "عرفنفسك",
    "عرفنيبنفسك",
)

_REQUIREMENT_GUIDANCE: dict[str, str] = {
    "agent_goal": (
        "ببساطة: ما العمل الذي تريد أن يقوم به الوكيل بدل الموظف؟ "
        "اختر مثالًا: الرد على العملاء، حجز المواعيد، متابعة الطلبات، "
        "أو البحث في ملفات الشركة."
    ),
    "deployment_channel": (
        "أين سيستخدم الناس الوكيل؟ مثلًا داخل الموقع، واتساب، تطبيق، "
        "أو نظام داخلي للموظفين."
    ),
    "data_sources": (
        "ما المعلومات التي سيقرأ منها الوكيل إجاباته؟ مثل ملفات PDF، "
        "أسئلة شائعة، قاعدة بيانات، أو محتوى الموقع."
    ),
    "agent_actions": (
        "هل تريد منه الرد فقط، أم تنفيذ إجراء أيضًا؟ مثل إنشاء حجز، "
        "تسجيل طلب، أو متابعة حالة طلب."
    ),
    "website_goal": (
        "ما النتيجة الأساسية التي تريدها من الموقع؟ مثل عرض الخدمات، "
        "بيع المنتجات، استقبال الطلبات، أو حجز المواعيد."
    ),
    "business_type": (
        "ما نشاط المشروع؟ مثل مطعم، متجر، عيادة، شركة خدمات، أو نشاط آخر."
    ),
    "features": (
        "اذكر أهم الوظائف التي يحتاجها المستخدم، مثل الطلبات، الدفع، "
        "الحجوزات، البحث، أو الإشعارات."
    ),
    "existing_website": (
        "هل لديك موقع يعمل الآن؟ أجب فقط: نعم، موجود حاليًا؛ أو لا، "
        "سيُنشأ من البداية."
    ),
    "expected_traffic": (
        "أعطني تقديرًا تقريبيًا للزيارات: قليلة، متوسطة، مرتفعة، "
        "أو عددًا شهريًا إن كنت تعرفه."
    ),
    "security_scope": (
        "اختر المطلوب: فحص أمني مرة واحدة، حماية من الهجمات، "
        "أو مراقبة أمنية مستمرة."
    ),
    "target_audience": (
        "من الأشخاص الذين تريد الوصول إليهم؟ مثل أصحاب الشركات، "
        "العائلات، الطلاب، أو فئة محددة."
    ),
    "preferred_style": (
        "صف الشكل الذي تفضله بكلمات بسيطة، مثل عصري، رسمي، بسيط، "
        "فاخر، أو مرح."
    ),
}


def department_label(department: Department) -> str:
    return DEPARTMENT_LABELS.get(department, department.value)


def ticket_status_label(status: TicketStatus) -> str:
    return TICKET_STATUS_LABELS.get(status, status.value)


def _normalize_text(value: str) -> str:
    normalized = value.casefold()
    normalized = normalized.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    normalized = normalized.replace("ى", "ي")
    return " ".join(_TEXT_SEPARATORS.sub(" ", normalized).split())


def _is_identity_question(message: str | None) -> bool:
    compact = _normalize_text(message or "").replace(" ", "")
    return any(signal in compact for signal in _IDENTITY_QUESTIONS)


def _requirement_guidance(requirement: RequirementDefinition) -> str:
    specific = _REQUIREMENT_GUIDANCE.get(requirement.key)
    if specific:
        return specific

    if requirement.value_kind is RequirementValueKind.BOOLEAN:
        return f"ببساطة، أجب بنعم أو لا: {requirement.question_ar}"
    if requirement.value_kind is RequirementValueKind.HUMAN_LANGUAGES:
        return "اذكر اللغة أو اللغات المطلوبة، مثل العربية أو الإنجليزية أو كلتيهما."
    if requirement.value_kind is RequirementValueKind.FEATURE_LIST:
        return "اذكر أهم ميزتين أو ثلاث تريدها، كل واحدة بكلمات بسيطة."
    return f"بصياغة أبسط: {requirement.question_ar} ويمكنك الإجابة بجملة قصيرة."


def _guided_final_attempt(requirement: RequirementDefinition | None) -> str:
    if requirement is None:
        return (
            "لن أكرر السؤال بالطريقة نفسها. اكتب النتيجة التي تريدها "
            "بجملة قصيرة، وسأحدد الخطوة التالية."
        )
    return (
        "لن أكرر السؤال بالطريقة نفسها. "
        f"{_requirement_guidance(requirement)} "
        "إذا لم يناسبك أي مثال، اكتب ما تريده بكلماتك."
    )


def _requirement_display(
    service_key: ServiceKey,
    key: str,
    value: str,
) -> tuple[str, str]:
    service = get_service(service_key)
    requirement = (
        next((item for item in service.requirements if item.key == key), None)
        if service
        else None
    )
    label = requirement.label_ar if requirement else key
    if requirement and requirement.value_kind is RequirementValueKind.BOOLEAN:
        if value == "yes":
            value = "نعم، يوجد حاليًا" if key == "existing_website" else "نعم"
        elif value == "no":
            value = "لا، سيُنشأ من البداية" if key == "existing_website" else "لا"
    return label, value


def format_ticket_draft(draft: TicketDraft) -> str:
    service = get_service(draft.service_key)
    service_name = service.name_ar if service else draft.service_key.value
    requirements = []
    for key, value in draft.requirements.items():
        label, display_value = _requirement_display(draft.service_key, key, value)
        requirements.append(f"- {label}: {display_value}")

    sections = [
        f"مسودة التذكرة - الإصدار {draft.version}",
        f"الخدمة: {service_name}",
        f"القسم المسؤول: {department_label(draft.primary_department)}",
        "المتطلبات:\n" + "\n".join(requirements),
    ]
    if draft.additional_features:
        sections.append(
            "المزايا الإضافية:\n"
            + "\n".join(f"- {item}" for item in draft.additional_features)
        )
    if draft.customer_notes:
        sections.append(
            "ملاحظات العميل:\n"
            + "\n".join(f"- {item}" for item in draft.customer_notes)
        )
    return "\n".join(sections)


def build_blocked_response(
    policy: PolicyDecision,
    stage: ConversationStage,
) -> AssistantResponse:
    if policy.action is PolicyAction.TEMPORARILY_SUSPEND:
        text = "تم إيقاف الطلبات مؤقتًا لهذه الجلسة بسبب كثافة الإرسال. حاول بعد قليل."
    else:
        text = "تعذر متابعة الطلب الآن بسبب حماية حركة الطلبات. انتظر قليلًا ثم حاول مجددًا."
    return AssistantResponse(text=text, policy_action=policy.action, stage=stage)


def _controlled_intent_response(
    decision: MessageDecision,
    conversation: ConversationState,
) -> str | None:
    if _is_identity_question(conversation.last_user_message):
        return (
            "أنا مساعد Travel-X الذكي لخدمات الشركة التقنية. أساعدك في اختيار "
            "الخدمة، جمع المتطلبات، وتجهيز التذكرة للقسم المختص."
        )
    if decision.primary_intent is MessageIntent.GREETING:
        return "مرحبًا بك. أنا مساعد Travel-X، ما الخدمة التقنية التي تحتاجها؟"
    if decision.primary_intent is MessageIntent.OFF_TOPIC:
        if conversation.counters.exact_repeat_count >= 1:
            return (
                "هذا السؤال خارج نطاق خدمات Travel-X. يمكنني مساعدتك في البرمجة، "
                "الاستضافة، الحماية، التسويق، أو التصميم."
            )
        return (
            "أنا مخصص لخدمات Travel-X التقنية مثل البرمجة والاستضافة والحماية والتسويق."
        )
    if decision.primary_intent is MessageIntent.ABUSE:
        return "سأساعدك في طلبك التقني. اذكر الخدمة أو النتيجة التي تريد الوصول إليها."
    if decision.primary_intent is MessageIntent.HUMAN_REQUEST:
        return "يمكنني تجهيز طلبك، لكن قناة التحويل المباشر لموظف لم تُربط بعد."
    if (
        decision.primary_intent is MessageIntent.UNKNOWN
        and conversation.current_service is None
    ):
        return "لم أفهم الطلب بعد. هل تريد موقعًا، تطبيقًا، وكيلًا ذكيًا، استضافة، حماية، أم تصميمًا؟"
    return None


def build_business_response(
    decision: MessageDecision,
    policy: PolicyDecision,
    collection: RequirementCollectionResult,
) -> AssistantResponse:
    service = collection.service
    conversation = collection.conversation
    controlled = _controlled_intent_response(decision, conversation)

    if controlled:
        text = controlled
    elif policy.action is PolicyAction.OFFER_HUMAN_HANDOFF:
        text = _guided_final_attempt(collection.next_requirement)
    elif policy.action is PolicyAction.EXPLAIN_DIFFERENTLY:
        if collection.next_requirement:
            text = _requirement_guidance(collection.next_requirement)
        elif service:
            text = (
                f"بصياغة أبسط: خدمة {service.name_ar} تعني {service.description_ar} "
                "اذكر النتيجة التي تريدها وسأكمل معك."
            )
        else:
            text = "اكتب ما تريد تنفيذه بجملة قصيرة، أو اختر: موقع، تطبيق، استضافة، حماية، تسويق، أو تصميم."
    elif service is None:
        text = "أحتاج إلى تفاصيل أكثر لتحديد الخدمة والقسم المناسبين. ما الذي تريد تنفيذه؟"
    elif (
        decision.primary_intent is MessageIntent.UNKNOWN
        and collection.next_requirement is not None
    ):
        text = "لم أفهم رسالتك الأخيرة. " + _requirement_guidance(
            collection.next_requirement
        )
    elif conversation.stage is ConversationStage.DRAFT_REVIEW:
        if conversation.ticket_draft is None:
            text = f"اكتملت المتطلبات الأساسية لخدمة {service.name_ar}."
        else:
            text = (
                f"اكتملت المتطلبات الأساسية لخدمة {service.name_ar}.\n"
                f"{format_ticket_draft(conversation.ticket_draft)}\n"
                "يمكنك إضافة أو حذف أو تعديل ميزة قبل التأكيد."
            )
    else:
        parts: list[str] = []
        if policy.action is PolicyAction.APPLY_PRICING_POLICY:
            parts.append(
                "يحدد القسم المختص التكلفة بعد مراجعة المتطلبات، ولا يقدم النظام سعرًا نهائيًا."
            )
        if decision.primary_intent in {
            MessageIntent.SERVICE_REQUEST,
            MessageIntent.SERVICE_QUESTION,
        }:
            parts.append(service.description_ar)
        if collection.next_requirement:
            parts.append(collection.next_requirement.question_ar)
        text = " ".join(parts) or (
            collection.next_requirement.question_ar
            if collection.next_requirement
            else "كيف يمكنني مساعدتك في هذه الخدمة؟"
        )

    conversation.last_assistant_response = text
    return AssistantResponse(
        text=text,
        policy_action=policy.action,
        stage=conversation.stage,
        service_key=service.key if service else None,
        primary_department=service.primary_department if service else None,
        missing_requirements=conversation.missing_requirements,
    )


def build_knowledge_response(
    *,
    text: str,
    policy_action: PolicyAction,
    stage: ConversationStage,
    service: ServiceDefinition | None,
    sources: list[KnowledgeSource],
    missing_requirements: list[str],
) -> AssistantResponse:
    return AssistantResponse(
        text=text,
        policy_action=policy_action,
        stage=stage,
        service_key=service.key if service else None,
        primary_department=service.primary_department if service else None,
        missing_requirements=missing_requirements,
        knowledge_sources=sources,
    )


def build_ticket_edit_response(
    decision: TicketFeatureDecision,
    edit_result: TicketEditResult,
    conversation: ConversationState,
) -> AssistantResponse:
    draft = edit_result.draft

    if edit_result.applied:
        operation_labels = {
            TicketEditOperation.ADD_FEATURE: "إضافة ميزة",
            TicketEditOperation.REMOVE_FEATURE: "حذف ميزة",
            TicketEditOperation.REPLACE_FEATURE: "تعديل ميزة",
            TicketEditOperation.ADD_NOTE: "إضافة ملاحظة",
        }
        change_lines = [
            f'- {operation_labels[change.operation]}: "{change.item}"'
            for change in edit_result.changes
        ]
        changes_text = "\n".join(change_lines)
        text = (
            "تم تطبيق التعديلات التالية:\n"
            f"{changes_text}\n"
            f"{format_ticket_draft(draft)}\n"
            "راجع أحدث إصدار قبل التأكيد."
        )
    elif edit_result.response_key == FeatureDecisionAction.REJECT_OFF_TOPIC.value:
        text = "لم أضف هذا النص لأنه لا يمثل ميزة مرتبطة بالخدمة الحالية."
    elif edit_result.response_key == FeatureDecisionAction.REJECT_UNSAFE.value:
        text = "لم أضف هذا الطلب لأنه غير مسموح أو غير مناسب لخدمات الشركة."
    elif edit_result.response_key == FeatureDecisionAction.SUGGEST_SEPARATE_SERVICE.value:
        suggested = get_service(decision.suggested_service)
        service_name = suggested.name_ar if suggested else "خدمة أخرى"
        text = (
            f"لم أضف الطلب إلى هذه المسودة لأنه أقرب إلى {service_name}. "
            "يمكن إنشاء طلب منفصل له."
        )
    elif edit_result.response_key == FeatureDecisionAction.DUPLICATE.value:
        text = "هذه الميزة أو الملاحظة موجودة بالفعل في المسودة."
    elif edit_result.response_key == "feature_not_found":
        text = "لم أجد الميزة المطلوبة داخل المسودة. اذكر اسمها كما ظهرت في الملخص."
    else:
        text = decision.clarification_question_ar or (
            "لم أتمكن من تحديد التعديل بأمان. وضح الميزة التي تريد إضافتها أو تغييرها."
        )

    conversation.last_assistant_response = text
    return AssistantResponse(
        text=text,
        policy_action=PolicyAction.CONTINUE,
        stage=conversation.stage,
        service_key=draft.service_key,
        primary_department=draft.primary_department,
        missing_requirements=conversation.missing_requirements,
    )
