import sqlite3
import pandas as pd
import os
import re


def sanitize_table_name(name: str) -> str:
    """Converts a filename/sheet name into a safe SQL table name."""
    name = os.path.splitext(name)[0]  # strip file extension
    name = re.sub(r'[^0-9a-zA-Z_]', '_', name)  # replace anything non-alphanumeric with _
    name = re.sub(r'_+', '_', name)  # collapse multiple underscores
    name = name.strip('_')
    if not name or name[0].isdigit():
        name = f"table_{name}"
    return name


MAX_ENUM_VALUES = 30   # list every value for columns with at most this many distinct values
TOP_K_VALUES = 5       # otherwise list the most frequent values
MAX_VALUE_CHARS = 40   # truncate long strings to keep the prompt small


def _short(value) -> str:
    text = str(value)
    return text if len(text) <= MAX_VALUE_CHARS else text[:MAX_VALUE_CHARS] + "..."


def get_schema(db_path: str, legacy_sampling: bool = False) -> str:
    """Describe the database for the LLM prompt.

    Text columns get example values so the model matches the stored format
    (e.g. 'USA' rather than 'United States'). Low-cardinality columns list ALL
    distinct values; others list the most frequent ones. legacy_sampling=True
    restores the original behaviour (first 5 distinct values) for comparison.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    schema_lines = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info('{table}');")
        columns = cursor.fetchall()
        col_names = [col[1] for col in columns]
        schema_lines.append(f"- {table}({', '.join(col_names)})")

        # add sample distinct values for text-like columns to show exact formatting
        for col in columns:
            col_name = col[1]
            col_type = col[2].upper()
            if "CHAR" in col_type or "TEXT" in col_type or col_type == "":
                try:
                    if legacy_sampling:
                        cursor.execute(f"SELECT DISTINCT \"{col_name}\" FROM \"{table}\" LIMIT 5;")
                        samples = [str(row[0]) for row in cursor.fetchall()]
                        if samples:
                            schema_lines.append(f"    {col_name} sample values: {samples}")
                        continue
                    cursor.execute(
                        f"SELECT COUNT(DISTINCT \"{col_name}\") FROM \"{table}\" WHERE \"{col_name}\" IS NOT NULL;"
                    )
                    n_distinct = cursor.fetchone()[0]
                    if n_distinct == 0:
                        continue
                    limit = n_distinct if n_distinct <= MAX_ENUM_VALUES else TOP_K_VALUES
                    cursor.execute(
                        f"SELECT \"{col_name}\" FROM \"{table}\" WHERE \"{col_name}\" IS NOT NULL "
                        f"GROUP BY \"{col_name}\" ORDER BY COUNT(*) DESC, \"{col_name}\" LIMIT {limit};"
                    )
                    samples = [_short(row[0]) for row in cursor.fetchall()]
                    if n_distinct <= MAX_ENUM_VALUES:
                        label = f"sample values (all {n_distinct} distinct)"
                    else:
                        label = f"sample values (top {limit} most frequent of {n_distinct} distinct)"
                    schema_lines.append(f"    {col_name} {label}: {samples}")
                except Exception:
                    pass

        cursor.execute(f"PRAGMA foreign_key_list('{table}');")
        fks = cursor.fetchall()
        for fk in fks:
            schema_lines.append(f"  FOREIGN KEY: {table}.{fk[3]} -> {fk[2]}.{fk[4]}")

    conn.close()
    return "Tables:\n" + "\n".join(schema_lines)


def convert_to_sqlite(uploaded_file, temp_dir: str) -> str:
    """Converts an uploaded CSV/Excel/SQLite file into a SQLite db and returns its path."""
    filename = uploaded_file.name.lower()
    db_path = os.path.join(temp_dir, "converted.db")

    def clean_dataframe(df):
        # strip whitespace from column names
        df.columns = [c.strip() for c in df.columns]
        # strip whitespace from string cell values
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].astype(str).str.strip()
        return df

    if filename.endswith((".db", ".sqlite", ".sqlite3")):
        raw_path = os.path.join(temp_dir, "user_uploaded.db")
        with open(raw_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return raw_path

    elif filename.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        df = clean_dataframe(df)
        conn = sqlite3.connect(db_path)
        table_name = sanitize_table_name(uploaded_file.name)
        df.to_sql(table_name, conn, index=False, if_exists="replace")
        conn.close()
        return db_path

    elif filename.endswith((".xlsx", ".xls")):
        excel_file = pd.ExcelFile(uploaded_file)
        conn = sqlite3.connect(db_path)
        for sheet_name in excel_file.sheet_names:
            df = excel_file.parse(sheet_name)
            df = clean_dataframe(df)
            table_name = sanitize_table_name(sheet_name)
            df.to_sql(table_name, conn, index=False, if_exists="replace")
        conn.close()
        return db_path

    else:
        raise ValueError("Unsupported file type.")