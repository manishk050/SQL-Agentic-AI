import os
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from pydantic import BaseModel

from agent import answer_question, describe_database

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "chinook.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
    )

client = genai.Client(api_key=GEMINI_API_KEY)

app = FastAPI(title="SQL Analyst Agent")

# Allow the local React dev server to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


@lru_cache(maxsize=1)
def _cached_db_info():
    # Computed once per server run -- schema + description don't change,
    # so there's no reason to hit the model every time the UI loads.
    return describe_database(client, DB_PATH)


@app.get("/db-info")
def db_info():
    try:
        return _cached_db_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
def query(req: QuestionRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    info = _cached_db_info()
    try:
        result = answer_question(client, DB_PATH, info["schema"], req.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if result.get("error") and result.get("result") is None:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.get("/health")
def health():
    return {"status": "ok"}
