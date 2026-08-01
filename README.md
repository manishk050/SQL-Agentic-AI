# SQL Analyst Agent

A minimal agentic SQL analyst: ask a question in plain English, and the
agent generates SQL, runs it against a database, and explains the result —
retrying on its own if the query fails.

```
React UI  →  FastAPI backend  →  Gemini 2.5 Flash  →  SQLite (Chinook)
```

## What's in here

```
backend/
  main.py          FastAPI app — /db-info and /query endpoints
  agent.py         The agent loop: schema introspection, SQL generation,
                    execution, retry-on-error, and result explanation
  chinook.db       Sample database (music store: artists, albums, invoices…)
  requirements.txt
  .env.example

frontend/
  src/App.jsx      UI: DB description, example-question chips, query bar,
                    results as a "receipt" with SQL + explanation + table
  src/App.css
  ...
```

## Run it

**Backend**

```bash
cd backend
python -m venv venv && source venv/bin/activate   # or your preferred env tool
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your Gemini API key (https://aistudio.google.com/apikey)
uvicorn main:app --reload
```

Runs on `http://localhost:8000`. Check `http://localhost:8000/health` first,
then `http://localhost:8000/db-info` — the first call to that endpoint takes
a few seconds since it asks Gemini to describe the schema; it's cached after
that.

**Frontend** (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173`. Open it, and you should see the database
description and clickable example questions load in.

## How the agent loop works

1. On first request, `describe_database()` sends the DB schema to Gemini
   once and asks for a plain-English description + example questions.
   Cached for the life of the server.
2. On each question, `answer_question()`:
   - asks Gemini to write a SQL query for the question
   - checks it isn't a write/schema-altering query (blocked for safety)
   - executes it against SQLite
   - if it errors, feeds the exact error back to Gemini and retries
     (up to 3 attempts total)
   - once it succeeds, asks Gemini for a short plain-English explanation
     of the result

That retry-on-error step is the actual "agentic" part — it's the
plan → act → observe → correct loop, just scoped to one tool (SQL).

## Swapping in a different database

Replace `backend/chinook.db` with any SQLite file and update `DB_PATH` in
`.env` — the schema introspection is generic, so the description and
example questions will regenerate for whatever tables are there.

## Known limitations (fine for a learning project, not for production)

- The forbidden-keyword check is a safety net, not a real sandbox — don't
  point this at a database with data you care about protecting.
- No auth on the API — anyone who can reach `localhost:8000` can query it.
- Single SQLite file, no connection pooling — fine for a demo, not for
  concurrent load.
