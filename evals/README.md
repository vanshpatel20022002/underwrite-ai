# Underwriting Evaluation Suite

Deterministic regression evals that run the full underwriting workflow against 5 fixed Calgary test cases and assert correctness of the output. Results are saved as proof artifacts in `reports/`.

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

- Full Docker stack running: `docker compose -f docker/docker-compose.yml up -d`
- Data seeded and model trained: `docker compose exec api python scripts/seed_data.py`
- `requests` installed in the local environment: `pip install requests`

---

## Running the evals

```bash
# Run all 5 cases (from the repo root)
python evals/run_eval.py

# Run against a non-default API
python evals/run_eval.py --api http://localhost:8000

# Run a single case by id
python evals/run_eval.py --case eval_001
```

The script exits **0** if all assertions pass and **non-zero** if any fail — suitable for CI.

---

## Output files

After a successful run, three files are written to `reports/`:

| File | Contents |
|---|---|
| `reports/eval_results.json` | Full per-case metrics, assertion counts, and flag outcomes in JSON |
| `reports/eval_summary.md` | Human-readable markdown matrix with summary stats and a resume proof section |
| `reports/eval_matrix.csv` | One row per case — open in Excel or paste into a spreadsheet |

**These results are generated from actual API workflow runs — not hardcoded.** Each case creates a real case in the database, runs the full LangGraph workflow, and evaluates the generated report.

---

## Example terminal output

```
Underwriting Eval Runner — 5 case(s) — API: http://localhost:8000
Timestamp: 2026-06-12T10:24:01Z
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

...

======================================================================
RESULTS: 5/5 passed  |  0 failed  |  0 error(s)
All eval cases passed.

  Saved: reports/eval_results.json
  Saved: reports/eval_matrix.csv
  Saved: reports/eval_summary.md
======================================================================
```

---

## Example eval_summary.md

```markdown
# Underwriting Evaluation Matrix

**Generated:** 2026-06-12T10:24:01Z
**API:** http://localhost:8000
**Eval set:** fixed regression cases, not a large benchmark

## Summary

| Metric | Value |
|---|---|
| Total cases | 5 |
| Cases passed | 5 |
| Pass rate | 100% |
| Total assertions passed | 32 |
| Total assertions failed | 0 |
| Avg confidence score | 0.87 |
| Avg risk score | 38 / 100 |
| Avg comparables returned | 4.8 |
| Proxy disclosure present | 5 / 5 cases |
| False transaction-price claims | 0 |

## Eval Matrix

| Case | Address | Value | Confidence | Risk | Comps | Recommendation | Assertions | Status |
| ---- | ------- | ----: | ---------: | ---: | ----: | -------------- | ---------: | ------ |
| eval_001 | 15 Deermeade Pl SE | $619,917 | 0.94 | 35 | 5 | review | 7/7 | ✅ PASS |
...
```

---

## Optional LLM evals (Ragas / DeepEval)

The eval runner automatically attempts to invoke the existing backend eval helpers at `backend/app/eval/`:

- **DeepEval** — answer relevancy check
- **Ragas** — faithfulness and answer relevancy
- **Citations check** — structural citation presence check

These require the relevant packages (`deepeval`, `ragas`, `datasets`) and an LLM provider key. If any dependency is missing, the eval is **silently skipped** — it does not affect the deterministic assertion results or the saved report files.

---

## Limitations

- Evals require a live API and seeded database — they cannot run offline.
- Each case takes 20–60 seconds because it runs the full multi-step workflow.
- The eval set is 5 fixed Calgary cases — this is a regression suite, not a benchmark.
- LLM eval quality (Ragas / DeepEval) depends on LLM availability and prompt stability.
