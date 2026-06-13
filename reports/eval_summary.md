# Underwriting Evaluation Matrix

**Generated:** 2026-06-12T10:24:01Z  
**API:** http://localhost:8000  
**Eval set:** `evals/underwriting_eval_cases.json` (fixed regression cases, not a large benchmark)  

---

## Summary

| Metric | Value |
|---|---|
| Total cases | 2 |
| Cases passed | 2 |
| Cases failed | 0 |
| Cases errored | 0 |
| Pass rate | 100% |
| Total assertions passed | 12 |
| Total assertions failed | 0 |
| Avg confidence score | 0.92 |
| Avg risk score | 35 / 100 |
| Avg comparables returned | 5.0 |
| Proxy disclosure present | 2 / 2 cases |
| False transaction-price claims | 0 |
| Unfinished page citation (`p.?`) issues | 0 |

---

## Eval Matrix

| Case | Address | Value | Confidence | Risk | Comps | Recommendation | Assertions | Status |
| ---- | ------- | ----: | ---------: | ---: | ----: | -------------- | ---------: | ------ |
| eval_001 | 15 Deermeade Pl SE | $619,917 | 0.94 | 35 | 5 | review | 7/7 | ✅ PASS |
| eval_002 | 185 Mckenzie Towne Dr SE | $648,204 | 0.89 | 35 | 5 | review | 5/5 | ✅ PASS |

---

## Resume Proof Summary

Evaluated 2 fixed underwriting cases with deterministic regression checks across valuation, comparable retrieval, risk scoring, memo safety, and disclosure quality. Passed 12/12 assertions with 100% case pass rate. All 2/2 cases include the required assessed-value proxy disclosure. Zero false transaction-price claims detected. Evaluated against a live LightGBM model trained on 156,755 Calgary residential assessment records.

---

_Results are generated from actual API workflow runs — not hardcoded._  
_Each case runs the full pipeline: ingestion → comp search → valuation → risk → human-review → report._