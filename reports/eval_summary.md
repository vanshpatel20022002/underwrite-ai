# Underwriting Evaluation Matrix

> **Results not yet generated.**
>
> Run the eval suite against a live stack to populate this file:
>
> ```bash
> # 1. Start the stack and seed data
> docker compose -f docker/docker-compose.yml up -d
> docker compose -f docker/docker-compose.yml exec api python scripts/seed_data.py
>
> # 2. Run all 5 eval cases (from the repo root)
> python evals/run_eval.py
> ```
>
> `reports/eval_summary.md`, `reports/eval_matrix.csv`, and `reports/eval_results.json`
> are written automatically after every run. See `evals/README.md` for prerequisites.

---

_This file is committed as a placeholder. The numbers below will reflect actual
API workflow runs once the stack has been seeded and the eval script executed._
