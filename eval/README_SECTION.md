## Evaluation

I evaluated the agent on a hand-written test set against the bundled Chinook database, because "it works on my demo" is not a measurement.

**Setup.** 41 answerable questions with gold SQL (simple filters, aggregations, multi-table joins, subqueries/HAVING, and value-format cases such as `USA` vs "United States"), 6 unanswerable questions, and 14 adversarial prompts (write/DDL requests, stacked statements, prompt injection, ATTACH/PRAGMA). Gold queries were run and checked manually. Metric: **execution accuracy**, i.e. the result set of the generated query is compared with the gold result set (not the SQL text). *Strict* requires identical columns; *relaxed* tolerates extra or reordered columns. Model: `openai/gpt-oss-120b`, temperature 0. n is small, so 95% Wilson intervals are reported.

**Reproduce.**
```
export GROQ_API_KEY=...
python eval/evaluate.py --variants full no_samples no_fk names_only --sleep 2
# results land in eval/results/summary.md
```

### Results

| Variant | First attempt | Final (strict) | 95% CI | Final (relaxed) |
|---|---|---|---|---|
| Full prompt (schema + FKs + sample values) | XX% | XX% | XX-XX% | XX% |
| Without sample values | XX% | XX% | | |
| Without foreign keys | XX% | XX% | | |
| Names only (neither) | XX% | XX% | | |

- **Self-correction:** first-attempt accuracy XX% rose to XX% after retries; N of M queries that errored on the first attempt recovered.
- **Safety:** 14 adversarial prompts, 0 database modifications. N refused by the model, N blocked by `sql_guard`, N passed as harmless read-only queries.
- **Latency:** p50 X.Xs, p95 X.Xs per query; median N tokens.

### Failure analysis

| Failure type | Count | Example | Fix / status |
|---|---|---|---|
| (fill in from `eval/results/failures_for_tagging.csv`) | | | |

### Known limitations
- The retry loop only reacts to execution errors, so queries that run but return wrong results are never corrected.
- `sql_guard` accepts only a plain `SELECT` root, so legitimate read-only `UNION` queries are rejected.
- There is no abstention path: unanswerable questions (missing columns) usually return an invented answer.
- Sample values come from `DISTINCT ... LIMIT 5`, which can miss the value a question refers to.
