"""
Core agent logic for the SQL/data-analyst agent.

Two responsibilities:
1. describe_database()  -> plain-English description + example questions
                            (runs once, cached by main.py)
2. answer_question()    -> the actual agent loop:
                            generate SQL -> execute -> if it fails,
                            feed the error back to the model and retry
"""

import json
import re
import sqlite3
from google import genai

MODEL_NAME = "gemini-3.5-flash"
MAX_RETRIES = 3

# Only allow read-only queries. This is a safety net, not a security
# guarantee -- don't point this at a production database.
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|CREATE|ATTACH|PRAGMA)\b",
    re.IGNORECASE,
)


def get_schema(db_path: str) -> str:
    """Introspect the SQLite DB and return a text description of its schema."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]

    schema_lines = []
    for table in tables:
        cur.execute(f'PRAGMA table_info("{table}")')
        cols = cur.fetchall()  # (cid, name, type, notnull, dflt_value, pk)
        col_desc = ", ".join(f"{c[1]} ({c[2]})" for c in cols)
        schema_lines.append(f"- {table}: {col_desc}")

    conn.close()
    return "\n".join(schema_lines)


def describe_database(client: genai.Client, db_path: str) -> dict:
    """
    Ask Gemini to describe the database in plain English and suggest
    example questions a user could ask. Called once and cached.
    """
    schema = get_schema(db_path)

    prompt = f"""You are looking at the schema of a SQLite database.

Schema:
{schema}

Respond with ONLY valid JSON (no markdown fences, no preamble) in this shape:
{{
  "description": "1-2 sentence plain-English description of what this database contains and what domain it's from",
  "example_questions": ["question 1", "question 2", "question 3", "question 4", "question 5"]
}}

The example_questions should be natural-language questions a non-technical
user could ask, answerable using only the tables/columns shown above."""

    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    text = response.text.strip()
    text = re.sub(r"^```json\s*|\s*```$", "", text.strip())

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Fall back to something sane rather than crashing the endpoint
        parsed = {
            "description": "A SQLite database (couldn't parse model output).",
            "example_questions": [],
        }

    parsed["schema"] = schema
    return parsed


def _generate_sql(client: genai.Client, schema: str, question: str, error_context: str = "") -> str:
    prompt = f"""You are a SQL analyst agent. Given this SQLite schema:

{schema}

Write a single read-only SQLite query (SELECT only) that answers this question:
"{question}"
{error_context}
Respond with ONLY the raw SQL query. No markdown fences, no explanation."""

    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    sql = response.text.strip()
    sql = re.sub(r"^```sql\s*|^```\s*|\s*```$", "", sql, flags=re.IGNORECASE).strip()
    return sql


def _explain_result(client: genai.Client, question: str, sql: str, rows: list) -> str:
    prompt = f"""Question: "{question}"
SQL used: {sql}
Result (first few rows): {rows[:5]}

Write a 1-2 sentence plain-English answer to the question based on this result."""
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return response.text.strip()


def answer_question(client: genai.Client, db_path: str, schema: str, question: str) -> dict:
    """
    The core agentic loop: generate SQL, execute it, and on failure feed
    the error back to the model for a retry (capped at MAX_RETRIES).
    """
    error_context = ""
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        sql = _generate_sql(client, schema, question, error_context)

        if FORBIDDEN_KEYWORDS.search(sql):
            return {
                "sql": sql,
                "result": None,
                "explanation": "The generated query attempted a write/schema operation and was blocked for safety.",
                "attempts": attempt,
                "error": "blocked_unsafe_query",
            }

        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            conn.close()

            result_rows = [dict(zip(columns, row)) for row in rows]
            explanation = _explain_result(client, question, sql, result_rows)

            return {
                "sql": sql,
                "result": result_rows,
                "explanation": explanation,
                "attempts": attempt,
                "error": None,
            }

        except sqlite3.Error as e:
            last_error = str(e)
            error_context = (
                f'\nYour previous attempt "{sql}" failed with error: {last_error}. '
                f"Fix the query and try again."
            )

    return {
        "sql": sql,
        "result": None,
        "explanation": None,
        "attempts": MAX_RETRIES,
        "error": f"Failed after {MAX_RETRIES} attempts. Last error: {last_error}",
    }
