"""Offline tests for the pipeline logic (no API key needed).

    python eval/test_pipeline.py

Covers: error-driven retry, empty-result retry (and not looping when the SQL is
unchanged), the SELECT-only guard, and the improved sample-value selection.
"""
import importlib.util
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("evaluate", HERE / "evaluate.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

from result_checks import is_suspicious_empty  # noqa: E402
from schema_utils import get_schema  # noqa: E402
from sql_guard import is_safe_select  # noqa: E402

DB = str(ROOT / "db" / "Chinook.db")


class Scripted(ev.LLM):
    """Returns queued SQL strings and records the prompts it was asked."""

    def __init__(self, replies):
        super().__init__("scripted")
        self.replies = list(replies)
        self.questions = []

    def generate_sql(self, question, schema):
        self.questions.append(question)
        return self.replies.pop(0), {"latency": 0.0, "prompt_tokens": 0, "completion_tokens": 0, "cached": True}


def test_is_suspicious_empty():
    assert is_suspicious_empty([])
    assert is_suspicious_empty([(0,)])
    assert is_suspicious_empty([(None,)])
    assert not is_suspicious_empty([(13,)])
    assert not is_suspicious_empty([(0, 1)])
    assert not is_suspicious_empty([("a",), ("b",)])
    assert not is_suspicious_empty(None)


def test_error_retry_recovers():
    llm = Scripted(["SELECT COUNT(*) FROM Customers;", "SELECT COUNT(*) FROM Customer;"])
    att = ev.run_pipeline(llm, "How many customers?", "schema", DB)
    assert len(att) == 2 and att[0]["error"] and att[1]["rows"] == [(59,)]
    assert "Previous attempt failed" in llm.questions[1]


def test_error_retry_is_capped():
    llm = Scripted(["SELECT * FROM nope;"] * 3)
    att = ev.run_pipeline(llm, "q", "schema", DB)
    assert len(att) == 3 and all(a["error"] for a in att)


def test_empty_result_retry_fixes_wrong_filter():
    llm = Scripted([
        "SELECT COUNT(*) FROM Customer WHERE Country = 'United States';",
        "SELECT COUNT(*) FROM Customer WHERE Country = 'USA';",
    ])
    att = ev.run_pipeline(llm, "How many customers are from the United States?", "schema", DB)
    assert att[0]["rows"] == [(0,)] and att[0]["empty_retry"]
    assert att[-1]["rows"] == [(13,)]
    assert "returned no rows or a zero" in llm.questions[1]


def test_empty_retry_keeps_legit_zero_when_sql_unchanged():
    sql = "SELECT COUNT(*) FROM Artist WHERE ArtistId < 0;"
    llm = Scripted([sql, sql])
    att = ev.run_pipeline(llm, "How many artists have a negative id?", "schema", DB)
    assert len(att) == 1 and att[0]["rows"] == [(0,)] and not att[0]["empty_retry"]


def test_empty_retry_can_be_disabled():
    llm = Scripted(["SELECT COUNT(*) FROM Customer WHERE Country = 'United States';"])
    att = ev.run_pipeline(llm, "q", "schema", DB, retry_empty=False)
    assert len(att) == 1 and att[0]["rows"] == [(0,)]


def test_empty_retry_happens_once():
    llm = Scripted(["SELECT 1 WHERE 1=0;", "SELECT 2 WHERE 1=0;"])
    att = ev.run_pipeline(llm, "q", "schema", DB)
    assert len(att) == 2  # one extra attempt, not a loop


def test_empty_retry_ignores_unsafe_replacement():
    llm = Scripted(["SELECT 1 WHERE 1=0;", "DELETE FROM Customer;"])
    att = ev.run_pipeline(llm, "q", "schema", DB)
    assert len(att) == 1 and att[0]["rows"] == []  # keeps the original result, never runs the write


def test_guard_blocks_writes_before_execution():
    llm = Scripted(["DELETE FROM Customer;"])
    att = ev.run_pipeline(llm, "q", "schema", DB)
    assert len(att) == 1 and not att[0]["safe"] and att[0]["rows"] is None
    assert not is_safe_select("SELECT 1; DROP TABLE Customer;")[0]
    assert not is_safe_select("ATTACH DATABASE 'x.db' AS x")[0]


def test_read_only_connection_rejects_writes():
    try:
        ev.execute(DB, "DELETE FROM Customer")
    except sqlite3.OperationalError:
        return
    raise AssertionError("write succeeded on a read-only connection")


def test_sampling_lists_all_values_for_low_cardinality():
    schema = get_schema(DB)
    country = [l for l in schema.splitlines() if l.strip().startswith("Country sample values (all 24 distinct)")]
    assert country and "'USA'" in country[0] and "'United Kingdom'" in country[0]
    legacy = get_schema(DB, legacy_sampling=True)
    legacy_country = [l for l in legacy.splitlines() if l.strip().startswith("Country sample values")]
    assert legacy_country and "'USA'" not in legacy_country[0]  # the original sampler never showed the stored value
    assert "top 5 most frequent of" in schema  # high-cardinality columns are summarised


def test_ablation_variants_strip_the_right_lines():
    schema = get_schema(DB)
    assert "sample values" not in ev.schema_variant(schema, "no_samples")
    assert "FOREIGN KEY" in ev.schema_variant(schema, "no_samples")
    assert "FOREIGN KEY" not in ev.schema_variant(schema, "no_fk")
    both = ev.schema_variant(schema, "names_only")
    assert "sample values" not in both and "FOREIGN KEY" not in both


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"\n{len(tests)} tests passed")
