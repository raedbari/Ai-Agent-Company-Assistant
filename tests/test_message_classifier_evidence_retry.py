import asyncio

from travelx_agent.application.message_classifier import classify_message


MESSAGE = (
    "أريد موقعًا جديدًا لمطعم، هدفه عرض قائمة الطعام واستقبال الطلبات، "
    "لا يوجد لدي موقع حالي، أحتاج الطلبات والحجوزات، "
    "واللغات العربية والإنجليزية."
)


class SequenceClassifier:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, str]] = []

    async def ainvoke(
        self,
        payload: dict[str, str],
    ) -> dict[str, object]:
        self.calls.append(payload)
        return self.responses.pop(0)


def test_classifier_repairs_invalid_evidence_without_losing_requirements() -> None:
    first_response = {
        "primary_intent": "service_request",
        "user_goal": "طلب تطوير موقع لمطعم",
        "service_candidates": [
            {
                "service_key": "website_development",
                "confidence": 1.0,
            }
        ],
        "extracted_requirements": [
            {
                "key": "business_type",
                "value": "مطعم",
                "evidence": "أريد موقعًا جديدًا لمطعم",
            },
            {
                "key": "website_goal",
                "value": "عرض قائمة الطعام واستقبال الطلبات",
                "evidence": (
                    "هدف عرض قائمة الطعام واستقبال الطلبات، "
                    "أحتاج الطلبات"
                ),
            },
            {
                "key": "features",
                "value": "الطلبات والحجوزات",
                "evidence": "أحتاج الطلبات والحجوزات",
            },
        ],
        "confidence": 0.98,
    }

    corrected_response = {
        "primary_intent": "service_request",
        "user_goal": "طلب تطوير موقع لمطعم",
        "service_candidates": [
            {
                "service_key": "website_development",
                "confidence": 1.0,
            }
        ],
        "extracted_requirements": [
            {
                "key": "website_goal",
                "value": "عرض قائمة الطعام واستقبال الطلبات",
                "evidence": "هدفه عرض قائمة الطعام واستقبال الطلبات",
            }
        ],
        "confidence": 0.98,
    }

    classifier = SequenceClassifier(
        [first_response, corrected_response]
    )

    decision = asyncio.run(
        classify_message(classifier, MESSAGE)
    )

    requirements = {
        item.key: item
        for item in decision.extracted_requirements
    }

    assert len(classifier.calls) == 2
    assert set(requirements) == {
        "business_type",
        "website_goal",
        "features",
    }
    assert (
        requirements["website_goal"].evidence
        == "هدفه عرض قائمة الطعام واستقبال الطلبات"
    )
    assert (
        "contiguous verbatim substring"
        in classifier.calls[1]["validation_feedback"]
    )