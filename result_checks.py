"""Helpers for spotting results that look like a wrong filter value rather than a real answer."""


def is_suspicious_empty(rows) -> bool:
    """True if a result has no rows, or is a single cell holding 0 or NULL.

    Typical cause: a text filter that does not match the stored value
    (e.g. Country = 'United States' when the data says 'USA'). The query runs
    without error, so the normal error-driven retry never fires.
    """
    if rows is None:
        return False
    if len(rows) == 0:
        return True
    return len(rows) == 1 and len(rows[0]) == 1 and (rows[0][0] is None or rows[0][0] == 0)


def empty_result_prompt(question: str, sql: str) -> str:
    return (
        f"{question}\n\nThe previous query ran but returned no rows or a zero/NULL value:\n{sql}\n"
        "Check that every text filter uses the exact stored values listed under 'sample values' "
        "(casing, abbreviations, spelling) and that the joins are correct. "
        "If the empty result is genuinely the correct answer, return the same SQL unchanged."
    )
