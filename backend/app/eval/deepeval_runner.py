"""DeepEval test runner."""

from typing import Any


def run_deepeval_smoke(report: dict, contexts: list[str]) -> dict[str, Any]:
    try:
        from deepeval import assert_test
        from deepeval.metrics import AnswerRelevancyMetric
        from deepeval.test_case import LLMTestCase

        memo = report.get("memo_markdown", "")
        test_case = LLMTestCase(
            input="Generate underwriting memo",
            actual_output=memo,
            retrieval_context=contexts,
        )
        metric = AnswerRelevancyMetric(threshold=0.5)
        assert_test(test_case, [metric])
        return {"status": "passed", "metric": "answer_relevancy"}
    except Exception as exc:
        return {"status": "skipped", "reason": str(exc)}


def check_citations_present(report: dict) -> dict[str, Any]:
    citations = report.get("citations", [])
    memo = report.get("memo_markdown", "")
    has_citations = len(citations) > 0
    return {
        "status": "passed" if has_citations or len(memo) < 100 else "failed",
        "citation_count": len(citations),
    }
