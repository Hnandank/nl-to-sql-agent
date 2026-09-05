import sqlglot
from sqlglot import exp

def is_safe_select(sql: str) -> tuple[bool, str]:
    """Returns (is_safe, reason). Only allows single SELECT statements."""
    try:
        parsed = sqlglot.parse(sql, read="sqlite")
    except Exception as e:
        return False, f"Could not parse SQL: {e}"

    if len(parsed) != 1:
        return False, "Only a single statement is allowed."

    statement = parsed[0]

    if not isinstance(statement, exp.Select):
        return False, "Only SELECT statements are allowed."

    # Block any write/DDL keywords that might sneak in as subqueries or CTEs
    forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter)
    for node in statement.walk():
        if isinstance(node[0], forbidden):
            return False, "Query contains a forbidden write/DDL operation."

    return True, ""