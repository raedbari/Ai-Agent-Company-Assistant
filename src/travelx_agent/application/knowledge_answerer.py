from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable

from travelx_agent.domain.knowledge import (
    KnowledgeAnswerResult,
    KnowledgeModelAnswer,
    KnowledgeSource,
)
from travelx_agent.domain.service_catalog import ServiceKey
from travelx_agent.infrastructure.knowledge_base import TravelXKnowledgeBase
from travelx_agent.prompts.knowledge_answer import KNOWLEDGE_ANSWER_PROMPT


def build_knowledge_answerer(model: BaseChatModel) -> Runnable:
    parser = PydanticOutputParser(pydantic_object=KnowledgeModelAnswer)
    prompt = KNOWLEDGE_ANSWER_PROMPT.partial(
        format_instructions=parser.get_format_instructions()
    )
    return prompt | model.bind(response_format={"type": "json_object"}) | parser


async def answer_from_knowledge(
    answerer: Runnable,
    knowledge_base: TravelXKnowledgeBase,
    question: str,
    service_key: ServiceKey | None,
    *,
    limit: int = 4,
    previous_answer: str | None = None,
    explain_differently: bool = False,
) -> KnowledgeAnswerResult:
    documents = knowledge_base.retrieve(question, service_key, limit=limit)
    retrieved_sources = {
        str(document.metadata["source_id"]): KnowledgeSource(
            source_id=str(document.metadata["source_id"]),
            title_ar=str(document.metadata["title_ar"]),
        )
        for document in documents
    }
    context = "\n\n".join(
        (
            f"[source_id={document.metadata['source_id']}]\n"
            f"{document.page_content}"
        )
        for document in documents
    )
    raw = await answerer.ainvoke(
        {
            "question": question,
            "context": context,
            "answer_mode": "rephrase" if explain_differently else "normal",
            "previous_answer": previous_answer or "none",
        }
    )
    model_answer = KnowledgeModelAnswer.model_validate(raw)
    valid_source_ids = [
        source_id
        for source_id in model_answer.source_ids
        if source_id in retrieved_sources
    ]

    if not model_answer.sufficient_context or not valid_source_ids:
        return KnowledgeAnswerResult(
            text=(
                "لا تتوفر لدي معلومات موثقة كافية للإجابة عن هذا السؤال. "
                "يمكنني تجهيز طلب للقسم المختص."
            ),
            sufficient_context=False,
        )
    return KnowledgeAnswerResult(
        text=model_answer.answer_ar,
        sources=[retrieved_sources[source_id] for source_id in valid_source_ids],
        sufficient_context=True,
    )