import streamlit as st
import sqlite3
import pandas as pd
import tempfile
import os
from agent import generate_sql
from sql_guard import is_safe_select
from schema_utils import get_schema, convert_to_sqlite

st.title("SQL Query Agent")

# --- Session state for rate limiting ---
if "query_count" not in st.session_state:
    st.session_state.query_count = 0

MAX_QUERIES_PER_SESSION = 10
MAX_RETRIES = 2

# --- File upload ---
uploaded_file = st.file_uploader(
    "Upload your own database or data file (optional)",
    type=["db", "sqlite", "sqlite3", "csv", "xlsx", "xls"]
)

if uploaded_file is not None:
    temp_dir = tempfile.mkdtemp()
    try:
        db_path = convert_to_sqlite(uploaded_file, temp_dir)
        st.success(f"Using uploaded file: {uploaded_file.name}")
    except Exception as e:
        st.error(f"Could not process file: {e}")
        st.stop()
else:
    db_path = "db/Chinook.db"
    st.info("No file uploaded — using the sample Chinook music store database.")

# --- Schema detection ---
schema = get_schema(db_path)

with st.expander("View detected schema"):
    st.text(schema)

# --- Question input ---
# question = st.text_input("Ask a question about the database:")

question = st.text_input(
    "Ask a question about the database:",
    placeholder="Ask a question to get a SQL query"
)

if st.session_state.query_count >= MAX_QUERIES_PER_SESSION:
    st.warning("You've reached the query limit for this session. Please refresh to start a new session.")
    st.stop()

# --- Query generation + execution loop ---
if question:
    sql = None
    with st.spinner("Generating SQL..."):
        sql = generate_sql(question, schema)

    for attempt in range(MAX_RETRIES + 1):
        safe, reason = is_safe_select(sql)
        if not safe:
            st.error(f"Blocked unsafe query: {reason}")
            sql = None
            break

        st.subheader(f"Generated SQL (attempt {attempt + 1})")
        st.code(sql, language="sql")

        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql(sql, conn)
            conn.close()

            st.subheader("Results")
            st.dataframe(df)

            st.session_state.query_count += 1
            break

        except Exception as e:
            if attempt < MAX_RETRIES:
                st.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                sql = generate_sql(
                    f"{question}\n\nPrevious attempt failed with error: {e}. Fix the SQL.",
                    schema
                )
            else:
                st.error(f"Failed after {MAX_RETRIES + 1} attempts: {e}")

# --- Data preview ---
def get_table_previews(db_path: str, n_rows: int = 3) -> dict:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    previews = {}
    for table in tables:
        try:
            df = pd.read_sql(f"SELECT * FROM '{table}' LIMIT {n_rows};", conn)
            previews[table] = df
        except Exception:
            continue

    conn.close()
    return previews

st.subheader("Data Preview")
previews = get_table_previews(db_path)

for table_name, df in previews.items():
    st.markdown(f"**{table_name}** ({len(df.columns)} columns)")
    st.dataframe(df)

st.markdown("---")
st.caption(
    "⚠️ This tool uses AI to generate SQL queries. Outputs may occasionally be inaccurate — please verify results independently."
)
st.caption("© 2026 All rights reserved.")