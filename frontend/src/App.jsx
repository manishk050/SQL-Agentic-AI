import { useEffect, useState } from "react";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [dbInfo, setDbInfo] = useState(null);
  const [dbInfoError, setDbInfoError] = useState(null);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sqlOpen, setSqlOpen] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/db-info`)
      .then((res) => {
        if (!res.ok) throw new Error(`Server responded ${res.status}`);
        return res.json();
      })
      .then(setDbInfo)
      .catch((err) => setDbInfoError(err.message));
  }, []);

  async function runQuestion(q) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setSqlOpen(true);

    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Something went wrong.");
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    runQuestion(question);
  }

  return (
    <div className="page">
      <header className="header">
        <span className="eyebrow">Agentic SQL</span>
        <h1>Ask your database</h1>

        {dbInfoError && (
          <p className="db-error">
            Couldn't reach the backend at {API_BASE} — is <code>uvicorn</code> running?
          </p>
        )}
        {!dbInfoError && !dbInfo && <p className="db-desc muted">Reading the schema…</p>}
        {dbInfo && <p className="db-desc">{dbInfo.description}</p>}
      </header>

      {dbInfo?.example_questions?.length > 0 && (
        <div className="chip-row">
          {dbInfo.example_questions.map((q) => (
            <button key={q} className="chip" onClick={() => { setQuestion(q); runQuestion(q); }}>
              {q}
            </button>
          ))}
        </div>
      )}

      <form className="query-bar" onSubmit={handleSubmit}>
        <span className="prompt-glyph">›</span>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Which country's customers have spent the most?"
          disabled={!dbInfo}
        />
        <button type="submit" disabled={!dbInfo || loading}>
          {loading ? "Running…" : "Run"}
        </button>
      </form>

      {error && <div className="error-card">{error}</div>}

      {result && (
        <section className="receipt">
          <div className="receipt-meta">
            <span>{result.result?.length ?? 0} rows</span>
            <span className="dot">·</span>
            <span>{result.attempts} attempt{result.attempts > 1 ? "s" : ""}</span>
          </div>

          {result.explanation && <p className="explanation">{result.explanation}</p>}

          <div className="sql-block">
            <button className="sql-toggle" onClick={() => setSqlOpen((v) => !v)}>
              {sqlOpen ? "▾" : "▸"} SQL used
            </button>
            {sqlOpen && <pre><code>{result.sql}</code></pre>}
          </div>

          {result.result?.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {Object.keys(result.result[0]).map((col) => (
                      <th key={col}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.result.map((row, i) => (
                    <tr key={i}>
                      {Object.values(row).map((val, j) => (
                        <td key={j}>{String(val)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
