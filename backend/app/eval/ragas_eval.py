"""Ragas evaluation runner for underwriting reports."""

from typing import Any


def run_ragas_eval(cases: list[dict]) -> dict[str, Any]:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, faithfulness

        dataset = Dataset.from_dict(
            {
                "question": [c["question"] for c in cases],
                "answer": [c["answer"] for c in cases],
                "contexts": [c["contexts"] for c in cases],
            }
        )
        result = evaluate(dataset, metrics=[faithfulness, answer_relevancy])
        return {"status": "completed", "scores": dict(result)}
    except Exception as exc:
        return {"status": "skipped", "reason": str(exc)}
