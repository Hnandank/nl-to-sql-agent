# NL to SQL Agent

A self-correcting natural language–to–SQL agent. Ask questions in plain English, and it generates, validates, and executes SQL against a database — either the bundled sample or your own uploaded file (SQLite, CSV, or Excel).

**Live demo:** [your-streamlit-url-here]

## Features

- **Natural language to SQL** using an LLM (Groq-hosted `openai/gpt-oss-120b`)
- **Multi-format upload** — works with SQLite (`.db`, `.sqlite`, `.sqlite3`), CSV, and Excel (`.xlsx`, `.xls`) files. Non-SQLite files are automatically converted into an in-memory SQLite database, with each Excel sheet becoming its own table.
- **Dynamic schema introspection** — detects tables, columns, and foreign keys from whatever file is loaded, instead of relying on a fixed schema
- **Sample-value awareness** — the schema passed to the LLM includes real sample values per column, so generated queries match the actual casing/format of the data (e.g. `'graduate'` vs `'Graduate'`) instead of guessing
- **Data cleaning on ingest** — strips whitespace from column names and string values, and sanitizes table names derived from filenames/sheet names
- **Safety guard** (`sqlglot`-based) — parses every generated query and blocks anything that isn't a single `SELECT` statement, rejecting INSERT/UPDATE/DELETE/DROP/ALTER before execution
- **Self-correction loop** — if a generated query fails to execute, the error message is fed back to the LLM for an automatic retry (up to 2 attempts)
- **Data preview** — displays every table's column count and first rows so users know what they're querying before asking anything
- **Session rate limiting** — caps queries per session to protect free-tier API usage

## Architecture


## Tech stack

- **Frontend/hosting:** Streamlit (Community Cloud)
- **LLM:** Groq API (`openai/gpt-oss-120b`)
- **SQL parsing/validation:** `sqlglot`
- **Data handling:** `pandas`, `openpyxl` (Excel support)
- **Database:** SQLite (bundled: Chinook sample DB; supports user-uploaded `.db`/`.csv`/`.xlsx` files)

## Running locally

```bash
git clone <your-repo-url>
cd nl-to-sql-agent
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml`:
```toml
GROQ_API_KEY = "your_groq_api_key"
```

Run:
```bash
streamlit run app.py
```

## Notes

- Only `SELECT` queries are ever executed — write/DDL operations are blocked before reaching the database, regardless of how the request is phrased.
- Uploaded files are converted and used only for the duration of the session; nothing is persisted between sessions.
- Sample dataset: [Chinook](https://github.com/lerocha/chinook-database), a public sample music store database.