# Underwriting Evaluation Suite

Deterministic regression evals that run the full underwriting workflow against fixed Calgary test cases and assert correctness of the output — no LLM scoring required for the core assertions.

---

## What is checked

Each eval case runs through the complete stack (ingestion → comp search → valuation → risk → human review → report) and verifies:

| Assertion | What it checks |
|---|---|
| `estimated_value_exists` | ML model returned a numeric estimate |
| `confidence_score_exists` | Confidence score (0–1) is present |
| `risk_score_exists` | Risk score (0–100) was computed |
| `min_comps` | At least 3 comparable sales were found |
| `memo_contains_proxy_disclosure` | Memo includes the required assessed-value proxy disclaimer |
| `memo_no_page_citation` | No `p.?` or unfinished citation markers appear |
| `memo_no_actual_transaction_claim` | Memo does not misrepresent proxy values as real transaction prices |
| `recommendation_is_review_or_reject_when_no_zoning` | Without a zoning document, recommendation is never `approve` |

These are **deterministic behavioral checks** — they do not depend on the exact LLM output text, only on structural guarantees.

---

## Eval cases

Defined in `underwriting_eval_cases.json`. Five fixed Calgary cases:

| ID | Description |
|---|---|
| `eval_001` | Standard single-family in Deer Run — known high comp density |
| `eval_002` | 4-bed larger home in McKenzie Towne |
| `eval_003` | Downtown condo — tests condo property type path |
| `eval_004` | Townhouse in Evanston — tests townhouse path |
| `eval_005` | Minimal input — missing optional fields (lot_size, year_built) |

---

## Prerequisites

- The full Docker stack running: `docker compose -f docker/docker-compose.yml up -d`
- Data seeded and model trained: `docker compose exec api python scripts/seed_data.py`
- `requests` installed: `pip install requests`

---

## Running the evals

```bash
# Run all 5 cases
python evals/run_eval.py

# Run against a non-default API
python evals/run_eval.py --api http://localhost:8000

# Run a single case by id
python evals/run_eval.py --case eval_001
```

The script exits **0** if all assertions pass and **non-zero** if any fail — suitable for CI.

### Example output

```
Underwriting Eval Runner — 5 case(s) — API: http://localhost:8000
======================================================================

[eval_001] Standard single-family — Deer Run
  Address: 15 Deermeade Pl SE, Calgary, AB
  ✓ Estimated value must be returned
  ✓ Confidence score (0–1) must be present
  ✓ At least 3 comparable sales required (got 5, need 3)
  ✓ Risk score must be present
  ✓ Memo must include assessed-value proxy disclaimer
  ✓ Memo must not contain 'p.?' citation artifacts
  ✓ Without a zoning document, recommendation must not be 'approve'
  → value=$619,917  conf=0.94  risk=35  comps=5  rec=review

======================================================================
RESULTS: 5/5 passed  |  0 failed  |  0 error(s)
All eval cases passed.
======================================================================
```

---

## Optional LLM evals (Ragas / DeepEval)

The eval runner automatically attempts to invoke the existing backend eval helpers at `backend/app/eval/`:

- **DeepEval** (`run_deepeval_smoke`) — answer relevancy check
- **Ragas** (`run_ragas_eval`) — faithfulness and answer relevancy
- **Citations check** (`check_citations_present`) — structural citation check

These require the relevant packages (`deepeval`, `ragas`, `datasets`) and an LLM API key. If any dependency is missing or the provider key is absent, the eval is **silently skipped** — it does not cause the run to fail.

---

## Limitations

- These evals require a live API and seeded database — they cannot run offline.
- Each case takes 20–60 seconds because it runs the full multi-step workflow.
- LLM eval quality (Ragas / DeepEval) depends on LLM availability and prompt stability.
- The eval cases use Calgary data; they will not pass meaningfully against a model trained on different data.
