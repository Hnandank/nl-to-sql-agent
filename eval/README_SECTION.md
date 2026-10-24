## Evaluation

"It works on my demo" is not a measurement, so the agent has a repeatable evaluation harness (`eval/`).

**Setup.** Two test sets, scored by **execution accuracy** (the result set of the generated SQL is compared with the result set of a hand-checked gold query, not the SQL text). *Strict* needs identical columns; *relaxed* tolerates extra or reordered columns.

| Set | Database | Questions | Purpose |
|---|---|---|---|
| `questions.json` | Chinook (public, likely seen by the model) | 41 answerable, 6 unanswerable, 14 adversarial | Broad coverage and safety |
| `questions_company.json` | Synthetic HR/projects DB (`make_company_db.py`) with codes such as `BLR`, `P0`, `on_leave` | 25 answerable | Data the model cannot have memorised; stresses value formats |

Model: `openai/gpt-oss-120b`, temperature 0. With few questions the confidence intervals are wide, so 95% Wilson intervals are shown.

**Reproduce**
```
python eval/test_pipeline.py                      # offline logic tests, no key needed
export GROQ_API_KEY=...                           # PowerShell: $env:GROQ_API_KEY="..."
python eval/evaluate.py --variants full no_samples no_fk names_only --sleep 2
python eval/make_company_db.py
python eval/evaluate.py --db eval/data/company.db --questions eval/questions_company.json \
       --variants full no_samples --results-dir eval/results_company --sleep 2
# baseline (behaviour before the fixes below)
python eval/evaluate.py --no-empty-retry --legacy-sampling --results-dir eval/results_baseline
```

### Baseline results (Chinook, before fixes)

| Prompt variant | First attempt | Final (strict) | 95% CI |
|---|---|---|---|
| Full (schema + foreign keys + sample values) | 97.6% | 97.6% | 87-100% |
| Without sample values | 100% | 100% | 91-100% |
| Without foreign keys | 95.1% | 95.1% | 84-99% |
| Names only | 95.1% | 95.1% | 84-99% |

The differences between variants are one or two questions, which is within noise. On Chinook, sample values showed no measurable benefit, probably because the model already knows this database.

- **Self-correction loop:** 0 of 41 queries raised an error, so the loop never fired and its benefit is unmeasured here. Its logic is covered by offline tests with injected failures (`test_pipeline.py`).
- **Safety:** 14 adversarial prompts (write/DDL requests, stacked statements, prompt injection, ATTACH/PRAGMA), **0 database modifications**. 12 were refused by the model, 1 was blocked by `sql_guard`, 1 was a harmless read of `sqlite_master`.
- **Cost:** p50 latency 2.8s (p95 15s); about 2,000 tokens per query, mostly the schema prompt.

### Failure analysis

| Question | What happened | Root cause | Fix |
|---|---|---|---|
| "How many customers are from the United States?" | Used `Country = 'United States'`; the data says `'USA'`. Query ran and returned 0, so no retry. | Sample values were `SELECT DISTINCT ... LIMIT 5`, which showed only 5 of 24 countries and not `USA`. | Low-cardinality columns now list **all** distinct values; others list the most frequent. Plus an empty-result retry. |

**Unanswerable questions (6):** 2 got an invented answer (e.g. a made-up 30% cost to compute "profit margin"), 2 returned an empty result with no explanation (`WHERE 1=0`), 1 abstained explicitly, 1 was refused by the write-denial rule. The agent has no real abstention path.

### Changes made after the baseline
1. `schema_utils.py`: list every value for columns with 30 or fewer distinct values, otherwise the 5 most frequent, labelled so the model knows whether the list is complete (prompt grows about 48% on Chinook).
2. `app.py`: when a query runs but returns no rows or a single 0/NULL, retry once with a hint to re-check filter values; the original result is kept if the model returns the same SQL.

### Results after changes

| Set | First attempt | Final (strict) | Notes |
|---|---|---|---|
| Chinook | XX% | XX% | |
| Company DB, baseline | XX% | XX% | |
| Company DB, after changes | XX% | XX% | |

### Known limitations
- Wrong-but-valid queries are only retried when the result is empty or zero; other wrong results pass through.
- `sql_guard` rejects legitimate read-only `UNION` queries.
- No abstention path for questions the schema cannot answer.
- The schema prompt dominates token cost on wide databases.
