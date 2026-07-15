from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Department(StrEnum):
    CYBTX = "cybtx"
    DESTINATION = "destination"
    TXSAAS = "txsaas"


class ServiceKey(StrEnum):
    HOSTING = "hosting"
    CYBERSECURITY = "cybersecurity"
    BACKUP = "backup"
    MONITORING = "monitoring"
    AI_AGENT = "ai_agent"
    WEBSITE_DEVELOPMENT = "website_development"
    MOBILE_APP = "mobile_app"
    SAAS_PLATFORM = "saas_platform"
    API_INTEGRATION = "api_integration"
    SOFTWARE_MAINTENANCE = "software_maintenance"
    MARKETING = "marketing"
    LOGO_DESIGN = "logo_design"
    VISUAL_IDENTITY = "visual_identity"
    SOCIAL_MEDIA_DESIGN = "social_media_design"


class RequirementValueKind(StrEnum):
    TEXT = "text"
    BOOLEAN = "boolean"
    HUMAN_LANGUAGES = "human_languages"
    FEATURE_LIST = "feature_list"


REQUIREMENT_LABELS_AR: dict[str, str] = {
    "website_type": "نوع الموقع أو النظام",
    "existing_website": "وجود موقع حالي",
    "expected_traffic": "الزيارات المتوقعة",
    "domain_status": "امتلاك النطاق",
    "backup_needed": "النسخ الاحتياطي",
    "security_needed": "الحماية والمراقبة",
    "asset_type": "الموقع أو النظام",
    "current_issue": "المشكلة الحالية",
    "security_scope": "نطاق الخدمة الأمنية",
    "urgency": "درجة الاستعجال",
    "backup_source": "مصدر النسخ الاحتياطي",
    "backup_frequency": "تكرار النسخ الاحتياطي",
    "retention_period": "مدة الاحتفاظ",
    "monitored_asset": "الموقع أو النظام المراد مراقبته",
    "monitoring_goal": "هدف المراقبة",
    "notification_channel": "قناة التنبيهات",
    "agent_goal": "هدف الوكيل الذكي",
    "deployment_channel": "مكان تشغيل الوكيل",
    "data_sources": "مصادر البيانات",
    "agent_actions": "إجراءات الوكيل",
    "languages": "لغات الواجهة والتواصل",
    "integrations": "الأنظمة المراد ربطها",
    "business_type": "مجال النشاط",
    "website_goal": "هدف الموقع",
    "features": "المزايا المطلوبة",
    "deadline": "الموعد المتوقع",
    "user_types": "أنواع المستخدمين",
    "platforms": "المنصات المطلوبة",
    "admin_panel": "لوحة الإدارة",
    "business_problem": "مشكلة العمل",
    "source_system": "النظام المصدر",
    "target_system": "النظام الهدف",
    "data_flow": "البيانات والإجراءات",
    "system_type": "نوع النظام",
    "technology": "التقنية الحالية",
    "requested_change": "التعديل المطلوب",
    "business_name": "اسم المشروع",
    "campaign_goal": "هدف الحملة",
    "target_audience": "الجمهور المستهدف",
    "channels": "القنوات التسويقية",
    "industry": "مجال المشروع",
    "preferred_style": "النمط المفضل",
    "preferred_colors": "الألوان المفضلة",
    "brand_personality": "طابع العلامة",
    "required_assets": "الملفات والتصاميم المطلوبة",
    "design_count": "عدد التصاميم",
    "content_type": "نوع المحتوى",
    "brand_assets": "ملفات الهوية",
}


class RequirementDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label_ar: str
    question_ar: str
    required: bool = True
    value_kind: RequirementValueKind = RequirementValueKind.TEXT


class ServiceDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: ServiceKey
    name_ar: str
    primary_department: Department
    supporting_departments: tuple[Department, ...] = ()
    description_ar: str
    requirements: tuple[RequirementDefinition, ...]


def _requirement(
    key: str,
    question: str,
    *,
    required: bool = True,
    value_kind: RequirementValueKind = RequirementValueKind.TEXT,
) -> RequirementDefinition:
    return RequirementDefinition(
        key=key,
        label_ar=REQUIREMENT_LABELS_AR.get(key, key),
        question_ar=question,
        required=required,
        value_kind=value_kind,
    )


SERVICE_CATALOG: dict[ServiceKey, ServiceDefinition] = {
    ServiceKey.HOSTING: ServiceDefinition(
        key=ServiceKey.HOSTING,
        name_ar="الاستضافة",
        primary_department=Department.CYBTX,
        description_ar="استضافة المواقع والأنظمة مع الحماية والنسخ الاحتياطي.",
        requirements=(
            _requirement("website_type", "ما نوع الموقع أو النظام المطلوب استضافته؟"),
            _requirement(
                "existing_website",
                "هل الموقع موجود حاليًا أم سيُنشأ من البداية؟",
                value_kind=RequirementValueKind.BOOLEAN,
            ),
            _requirement("expected_traffic", "ما عدد الزيارات المتوقع تقريبًا؟"),
            _requirement(
                "domain_status",
                "هل تملك دومين حاليًا؟",
                value_kind=RequirementValueKind.BOOLEAN,
            ),
            _requirement(
                "backup_needed",
                "هل تحتاج إلى نسخ احتياطي؟",
                value_kind=RequirementValueKind.BOOLEAN,
            ),
            _requirement(
                "security_needed",
                "هل تحتاج إلى حماية أو مراقبة أمنية إضافية؟",
                value_kind=RequirementValueKind.BOOLEAN,
            ),
        ),
    ),
    ServiceKey.CYBERSECURITY: ServiceDefinition(
        key=ServiceKey.CYBERSECURITY,
        name_ar="الأمن السيبراني",
        primary_department=Department.CYBTX,
        description_ar="حماية المواقع والأنظمة ومراجعة المشكلات والمخاطر الأمنية.",
        requirements=(
            _requirement("asset_type", "ما الموقع أو النظام الذي تريد حمايته؟"),
            _requirement("current_issue", "هل توجد مشكلة أو هجمات حالية؟"),
            _requirement("security_scope", "ما النطاق المطلوب: فحص أم حماية أم مراقبة مستمرة؟"),
            _requirement("urgency", "ما درجة استعجال الطلب؟"),
        ),
    ),
    ServiceKey.BACKUP: ServiceDefinition(
        key=ServiceKey.BACKUP,
        name_ar="النسخ الاحتياطي",
        primary_department=Department.CYBTX,
        description_ar="إعداد نسخ احتياطية مناسبة للمواقع والأنظمة.",
        requirements=(
            _requirement("backup_source", "ما البيانات أو النظام المطلوب نسخه؟"),
            _requirement("backup_frequency", "كم مرة تريد إنشاء النسخة الاحتياطية؟"),
            _requirement("retention_period", "ما مدة الاحتفاظ المطلوبة بالنسخ؟"),
        ),
    ),
    ServiceKey.MONITORING: ServiceDefinition(
        key=ServiceKey.MONITORING,
        name_ar="المراقبة التقنية والأمنية",
        primary_department=Department.CYBTX,
        description_ar="مراقبة توافر الأنظمة والمخاطر والتنبيهات.",
        requirements=(
            _requirement("monitored_asset", "ما الموقع أو النظام المطلوب مراقبته؟"),
            _requirement("monitoring_goal", "ما الأحداث أو المشكلات التي تريد مراقبتها؟"),
            _requirement("notification_channel", "كيف تريد استلام التنبيهات؟"),
        ),
    ),
    ServiceKey.AI_AGENT: ServiceDefinition(
        key=ServiceKey.AI_AGENT,
        name_ar="وكيل الذكاء الاصطناعي",
        primary_department=Department.CYBTX,
        supporting_departments=(Department.TXSAAS,),
        description_ar="بناء وكيل ذكي لخدمة العملاء أو تنفيذ مهام داخل موقع أو نظام.",
        requirements=(
            _requirement("agent_goal", "ما المهمة الأساسية التي تريد من الوكيل تنفيذها؟"),
            _requirement("deployment_channel", "أين سيعمل الوكيل: موقع أم تطبيق أم نظام داخلي؟"),
            _requirement("data_sources", "ما الملفات أو البيانات التي سيعتمد عليها؟"),
            _requirement("agent_actions", "هل سيجيب فقط أم سينفذ حجوزات أو طلبات أيضًا؟"),
            _requirement(
                "languages",
                "ما اللغات التي سيتحدث بها الوكيل، مثل العربية أو الإنجليزية؟",
                value_kind=RequirementValueKind.HUMAN_LANGUAGES,
            ),
            _requirement("integrations", "هل يجب ربطه بأنظمة خارجية؟", required=False),
        ),
    ),
    ServiceKey.WEBSITE_DEVELOPMENT: ServiceDefinition(
        key=ServiceKey.WEBSITE_DEVELOPMENT,
        name_ar="تطوير المواقع",
        primary_department=Department.TXSAAS,
        description_ar="تصميم وتطوير مواقع تعريفية ومتاجر ومنصات ويب.",
        requirements=(
            _requirement("business_type", "ما مجال المشروع أو النشاط؟"),
            _requirement("website_goal", "ما الهدف الأساسي من الموقع؟"),
            _requirement(
                "existing_website",
                "هل يوجد موقع حالي أم سيُنشأ من البداية؟",
                value_kind=RequirementValueKind.BOOLEAN,
            ),
            _requirement(
                "features",
                "ما أهم المزايا المطلوبة في الموقع؟",
                value_kind=RequirementValueKind.FEATURE_LIST,
            ),
            _requirement(
                "languages",
                "ما لغات واجهة الموقع المطلوبة، مثل العربية أو الإنجليزية؟",
                value_kind=RequirementValueKind.HUMAN_LANGUAGES,
            ),
            _requirement("deadline", "هل يوجد موعد متوقع للتسليم؟", required=False),
        ),
    ),
    ServiceKey.MOBILE_APP: ServiceDefinition(
        key=ServiceKey.MOBILE_APP,
        name_ar="تطبيق الهاتف",
        primary_department=Department.TXSAAS,
        description_ar="تطوير تطبيقات الهاتف ولوحات الإدارة والتكاملات.",
        requirements=(
            _requirement("user_types", "من أنواع المستخدمين الذين سيستخدمون التطبيق؟"),
            _requirement("platforms", "هل تريد التطبيق لأندرويد أم آيفون أم كليهما؟"),
            _requirement(
                "features",
                "ما أهم المزايا المطلوبة؟",
                value_kind=RequirementValueKind.FEATURE_LIST,
            ),
            _requirement(
                "admin_panel",
                "هل تحتاج إلى لوحة إدارة؟",
                value_kind=RequirementValueKind.BOOLEAN,
            ),
            _requirement("integrations", "هل توجد أنظمة يجب ربط التطبيق بها؟", required=False),
        ),
    ),
    ServiceKey.SAAS_PLATFORM: ServiceDefinition(
        key=ServiceKey.SAAS_PLATFORM,
        name_ar="منصة برمجية",
        primary_department=Department.TXSAAS,
        description_ar="بناء أنظمة شركات ومنصات برمجية قابلة للاشتراك.",
        requirements=(
            _requirement("business_problem", "ما المشكلة التي ستعالجها المنصة؟"),
            _requirement("user_types", "من أنواع المستخدمين؟"),
            _requirement(
                "features",
                "ما أهم الوظائف المطلوبة؟",
                value_kind=RequirementValueKind.FEATURE_LIST,
            ),
            _requirement("admin_panel", "ما الوظائف المطلوبة في لوحة الإدارة؟"),
            _requirement("integrations", "هل يجب ربطها بأنظمة أخرى؟", required=False),
        ),
    ),
    ServiceKey.API_INTEGRATION: ServiceDefinition(
        key=ServiceKey.API_INTEGRATION,
        name_ar="ربط الأنظمة",
        primary_department=Department.TXSAAS,
        description_ar="ربط المواقع والتطبيقات بالأنظمة والواجهات البرمجية.",
        requirements=(
            _requirement("source_system", "ما النظام الأول المطلوب ربطه؟"),
            _requirement("target_system", "ما النظام الآخر المطلوب الربط معه؟"),
            _requirement("data_flow", "ما البيانات أو الإجراءات التي ستنتقل بين النظامين؟"),
        ),
    ),
    ServiceKey.SOFTWARE_MAINTENANCE: ServiceDefinition(
        key=ServiceKey.SOFTWARE_MAINTENANCE,
        name_ar="صيانة البرمجيات",
        primary_department=Department.TXSAAS,
        description_ar="صيانة المواقع والتطبيقات وتطوير المزايا ومعالجة المشكلات.",
        requirements=(
            _requirement("system_type", "ما نوع الموقع أو التطبيق؟"),
            _requirement("technology", "ما التقنية المستخدمة إن كنت تعرفها؟"),
            _requirement("requested_change", "ما المشكلة أو التعديل المطلوب؟"),
            _requirement("urgency", "ما درجة استعجال الطلب؟"),
        ),
    ),
    ServiceKey.MARKETING: ServiceDefinition(
        key=ServiceKey.MARKETING,
        name_ar="التسويق",
        primary_department=Department.DESTINATION,
        description_ar="إعداد حملات ومواد تسويقية للمشاريع.",
        requirements=(
            _requirement("business_name", "ما اسم المشروع أو النشاط؟"),
            _requirement("campaign_goal", "ما الهدف من الحملة؟"),
            _requirement("target_audience", "من الجمهور المستهدف؟"),
            _requirement("channels", "ما القنوات أو المنصات المطلوبة؟"),
        ),
    ),
    ServiceKey.LOGO_DESIGN: ServiceDefinition(
        key=ServiceKey.LOGO_DESIGN,
        name_ar="تصميم الشعار",
        primary_department=Department.DESTINATION,
        description_ar="تصميم شعار يعكس مجال المشروع والجمهور المستهدف.",
        requirements=(
            _requirement("business_name", "ما اسم المشروع؟"),
            _requirement("industry", "ما مجال المشروع؟"),
            _requirement("target_audience", "من الجمهور المستهدف؟"),
            _requirement("preferred_style", "ما النمط الذي تفضله؟"),
            _requirement("preferred_colors", "هل توجد ألوان مفضلة؟", required=False),
        ),
    ),
    ServiceKey.VISUAL_IDENTITY: ServiceDefinition(
        key=ServiceKey.VISUAL_IDENTITY,
        name_ar="الهوية البصرية",
        primary_department=Department.DESTINATION,
        description_ar="إنشاء هوية بصرية متكاملة للمشروع.",
        requirements=(
            _requirement("business_name", "ما اسم المشروع؟"),
            _requirement("industry", "ما مجال المشروع؟"),
            _requirement("target_audience", "من الجمهور المستهدف؟"),
            _requirement("brand_personality", "ما الطابع الذي تريد أن تعكسه الهوية؟"),
            _requirement("required_assets", "ما الملفات والتصاميم المطلوبة؟"),
        ),
    ),
    ServiceKey.SOCIAL_MEDIA_DESIGN: ServiceDefinition(
        key=ServiceKey.SOCIAL_MEDIA_DESIGN,
        name_ar="تصاميم التواصل الاجتماعي",
        primary_department=Department.DESTINATION,
        description_ar="إنشاء تصاميم وحزم محتوى لمنصات التواصل الاجتماعي.",
        requirements=(
            _requirement("platforms", "ما منصات التواصل المطلوبة؟"),
            _requirement("design_count", "كم عدد التصاميم المطلوبة؟"),
            _requirement("content_type", "ما نوع المحتوى؟"),
            _requirement("brand_assets", "هل توجد هوية أو ملفات يجب الالتزام بها؟"),
        ),
    ),
}


SERVICE_ALIASES: dict[str, ServiceKey] = {
    "website": ServiceKey.WEBSITE_DEVELOPMENT,
    "websites": ServiceKey.WEBSITE_DEVELOPMENT,
    "web_development": ServiceKey.WEBSITE_DEVELOPMENT,
    "website_integration": ServiceKey.AI_AGENT,
    "ai_agents": ServiceKey.AI_AGENT,
    "chatbot": ServiceKey.AI_AGENT,
    "saas_system": ServiceKey.SAAS_PLATFORM,
    "maintenance": ServiceKey.SOFTWARE_MAINTENANCE,
    "logo": ServiceKey.LOGO_DESIGN,
    "branding": ServiceKey.VISUAL_IDENTITY,
}


def normalize_service_key(value: str | ServiceKey) -> ServiceKey:
    if isinstance(value, ServiceKey):
        return value
    normalized = value.strip().lower()
    try:
        return ServiceKey(normalized)
    except ValueError:
        alias = SERVICE_ALIASES.get(normalized)
        if alias is None:
            raise ValueError(f"Unsupported service key: {value}") from None
        return alias


def get_service(value: str | ServiceKey | None) -> ServiceDefinition | None:
    if value is None:
        return None
    try:
        return SERVICE_CATALOG[normalize_service_key(value)]
    except ValueError:
        return None


def catalog_prompt_context() -> str:
    lines: list[str] = []
    for service in SERVICE_CATALOG.values():
        requirement_keys = ", ".join(item.key for item in service.requirements)
        lines.append(
            f"- {service.key.value}: {service.name_ar}; keys=[{requirement_keys}]"
        )
    return "\n".join(lines)