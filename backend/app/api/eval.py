from fastapi import APIRouter

from app.eval.deepeval_runner import check_citations_present, run_deepeval_smoke
from app.eval.dspy_program import optimize_report_program
from app.eval.ragas_eval import run_ragas_eval

router = APIRouter()


@router.post("/ragas")
async def run_ragas(cases: list[dict]):
    return run_ragas_eval(cases)


@router.post("/deepeval")
async def run_deepeval(report: dict, contexts: list[str]):
    citation_check = check_citations_present(report)
    relevancy = run_deepeval_smoke(report, contexts)
    return {"citation_check": citation_check, "relevancy": relevancy}


@router.post("/dspy/optimize")
async def dspy_optimize(examples: list[dict]):
    return optimize_report_program(examples)
