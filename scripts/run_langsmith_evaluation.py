import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid5

from langsmith import Client, aevaluate
from langsmith.schemas import Example, Run

from travelx_agent.application.message_classifier import (
    build_message_classifier,
    classify_message,
)
from travelx_agent.core.config import get_settings
from travelx_agent.infrastructure.model import build_chat_model


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = PROJECT_ROOT / "evaluations" / "travelx_semantic_cases.json"
EXAMPLE_NAMESPACE = UUID("18d87898-241f-49d6-a1e2-15c76b57f218")


def load_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def build_evaluation_client() -> Client:
    settings = get_settings()
    if not settings.langsmith_api_key:
        raise RuntimeError("LANGSMITH_API_KEY is required for evaluation")
    return Client(
        api_url=settings.langsmith_endpoint,
        api_key=settings.langsmith_api_key,
        hide_inputs=False,
        hide_outputs=False,
    )


def publish_dataset(client: Client, dataset_name: str, cases: list[dict]) -> None:
    if client.has_dataset(dataset_name=dataset_name):
        dataset = client.read_dataset(dataset_name=dataset_name)
    else:
        dataset = client.create_dataset(
            dataset_name,
            description=(
                "Synthetic regression cases for Travel-X routing and semantic extraction"
            ),
            metadata={"source": "repository", "contains_real_customer_data": False},
        )

    examples = [
        {
            "id": str(uuid5(EXAMPLE_NAMESPACE, case["name"])),
            "inputs": case["inputs"],
            "outputs": case["outputs"],
            "metadata": {"case_name": case["name"]},
            "split": ["regression"],
        }
        for case in cases
    ]
    example_ids = [example["id"] for example in examples]
    existing_ids = {
        str(example.id)
        for example in client.list_examples(
            dataset_id=dataset.id,
            example_ids=example_ids,
        )
    }
    examples_to_create = [
        example for example in examples if example["id"] not in existing_ids
    ]
    examples_to_update = [
        example for example in examples if example["id"] in existing_ids
    ]

    if examples_to_create:
        client.create_examples(
            dataset_id=dataset.id,
            examples=examples_to_create,
        )
    if examples_to_update:
        client.update_examples(
            dataset_id=dataset.id,
            updates=examples_to_update,
        )

    print(
        f"Dataset synchronized: {dataset_name} "
        f"(created={len(examples_to_create)}, updated={len(examples_to_update)})"
    )


def _predicted_requirements(run: Run) -> dict[str, str]:
    outputs = run.outputs or {}
    return {
        item["key"]: item["value"]
        for item in outputs.get("extracted_requirements", [])
    }


def intent_accuracy(run: Run, example: Example) -> dict:
    predicted = (run.outputs or {}).get("primary_intent")
    expected = (example.outputs or {}).get("primary_intent")
    return {"key": "intent_accuracy", "score": predicted == expected}


def service_accuracy(run: Run, example: Example) -> dict:
    expected = (example.outputs or {}).get("service_key")
    if expected is None:
        return {"key": "service_accuracy", "score": True}
    candidates = (run.outputs or {}).get("service_candidates", [])
    predicted = candidates[0].get("service_key") if candidates else None
    return {"key": "service_accuracy", "score": predicted == expected}


def requirement_accuracy(run: Run, example: Example) -> dict:
    expected = example.outputs or {}
    predicted = _predicted_requirements(run)
    required = set(expected.get("required_requirement_keys", []))
    forbidden = set(expected.get("forbidden_requirement_keys", []))
    required_present = required.issubset(predicted)
    forbidden_absent = forbidden.isdisjoint(predicted)

    values_match = True
    for key, fragment in expected.get("requirement_value_contains", {}).items():
        values_match = values_match and fragment in predicted.get(key, "")

    return {
        "key": "requirement_accuracy",
        "score": required_present and forbidden_absent and values_match,
    }


def pricing_accuracy(run: Run, example: Example) -> dict:
    predicted = (run.outputs or {}).get("pricing_requested")
    expected = (example.outputs or {}).get("pricing_requested")
    return {"key": "pricing_accuracy", "score": predicted == expected}


async def run_experiment(client: Client, dataset_name: str) -> None:
    settings = get_settings()
    classifier = build_message_classifier(build_chat_model(settings))

    async def predict(inputs: dict) -> dict:
        context = json.dumps(
            inputs.get("conversation_context", {}),
            ensure_ascii=False,
        )
        decision = await classify_message(classifier, inputs["message"], context)
        return decision.model_dump(mode="json")

    await aevaluate(
        predict,
        data=dataset_name,
        evaluators=[
            intent_accuracy,
            service_accuracy,
            requirement_accuracy,
            pricing_accuracy,
        ],
        experiment_prefix="travelx-semantic",
        description="Travel-X semantic routing regression",
        metadata={
            "model": settings.openrouter_model,
            "prompt_version": "semantic-router-v2",
        },
        max_concurrency=1,
        num_repetitions=1,
        client=client,
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--publish-only",
        action="store_true",
        help="Publish or update the dataset without calling the model",
    )
    args = parser.parse_args()

    settings = get_settings()
    client = build_evaluation_client()
    cases = load_cases()
    publish_dataset(client, settings.langsmith_dataset, cases)
    if not args.publish_only:
        await run_experiment(client, settings.langsmith_dataset)


if __name__ == "__main__":
    asyncio.run(main())