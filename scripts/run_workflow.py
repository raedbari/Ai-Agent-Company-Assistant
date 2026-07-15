import asyncio
import json
import sys
from uuid import uuid4

from travelx_agent.application.knowledge_answerer import build_knowledge_answerer
from travelx_agent.application.message_classifier import build_message_classifier
from travelx_agent.core.config import get_settings
from travelx_agent.domain.conversation_state import ConversationState
from travelx_agent.graph.workflow import build_customer_workflow
from travelx_agent.infrastructure.knowledge_base import TravelXKnowledgeBase
from travelx_agent.infrastructure.model import build_chat_model


async def main() -> None:
    message = " ".join(sys.argv[1:]).strip()
    if not message:
        raise SystemExit("Pass a customer message as a command argument")

    settings = get_settings()
    model = build_chat_model(settings)
    classifier = build_message_classifier(model)
    knowledge_answerer = build_knowledge_answerer(model)
    knowledge_base = TravelXKnowledgeBase.from_json_file(settings.knowledge_file)
    workflow = build_customer_workflow(
        classifier,
        settings,
        knowledge_answerer=knowledge_answerer,
        knowledge_base=knowledge_base,
    )

    result = await workflow.ainvoke(
        {
            "message": message,
            "conversation": ConversationState(session_id=str(uuid4())),
        }
    )
    serializable = {
        key: value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        for key, value in result.items()
    }
    print(json.dumps(serializable, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())