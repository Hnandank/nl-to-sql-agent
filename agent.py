from groq import Groq
import streamlit as st
import re

client = Groq(api_key=st.secrets["GROQ_API_KEY"])

def generate_sql(question: str, schema: str) -> str:
    prompt = f"""You are a SQL expert. Given this database schema:

{schema}

Write a single SQLite SELECT query to answer this question:
"{question}"

Rules:
- Only output the raw SQL query, nothing else.
- Do not use markdown formatting or code fences.
- Only generate SELECT statements. Never write/modify data.
- Use proper JOINs based on the foreign keys shown in the schema.
- Match text values EXACTLY as shown in the "sample values" for each column, including case and spelling (e.g. if sample values show "graduate", do not write "Graduate").
- For yes/no or boolean-looking text columns, use the exact string values shown in samples (e.g. 'yes'/'no'), not 1/0, unless the samples show numeric values.
- If the request asks you to modify, delete, or drop data, respond with exactly: SELECT 'Request denied: read-only agent' AS Answer;
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    raw = response.choices[0].message.content.strip()
    clean = re.sub(r'\x1b\[[0-9;]*m', '', raw)
    return clean