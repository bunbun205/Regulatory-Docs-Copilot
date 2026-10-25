import { useRef, useState } from "react";
import { client, getApiKey } from "../api";
import type { components } from "../types/api";

type ErrorEnvelope = {
  error?: { message?: string; request_id?: string };
};

export default function AskView() {
  const [question, setQuestion] = useState("");
  const [answerData, setAnswerData] = useState<components["schemas"]["AskResponse"] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const inFlight = useRef(false);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (inFlight.current || !question.trim()) return;
    inFlight.current = true;
    setLoading(true);
    setError("");
    setAnswerData(null);
    try {
      const { data, error: apiError, response } = await client.POST("/v1/ask", {
        headers: { "X-API-Key": getApiKey() || "" },
        body: { query: question.trim() }
      });
      if (!response.ok) {
        const envelope = apiError as ErrorEnvelope | undefined;
        const message = envelope?.error?.message || `Request failed (HTTP ${response.status}).`;
        const requestId = envelope?.error?.request_id || response.headers.get("X-Request-ID");
        setError(requestId ? `${message} Request ID: ${requestId}` : message);
      } else if (data) {
        setAnswerData(data);
      }
    } catch {
      setError("Could not reach the API. Check that the local services are running and try again.");
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Ask (Grounded RAG)</h2>
      <form onSubmit={handleAsk}>
        <label htmlFor="ask-question">Question</label>
        <textarea id="ask-question" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask a question..." disabled={loading} />
        <button type="submit" disabled={loading || !question.trim()}>{loading ? "Asking..." : "Ask"}</button>
      </form>

      {loading && <div className="loading">Thinking...</div>}
      {error && <div className="error" role="alert">{error}</div>}
      {answerData && (
        <div style={{ marginTop: "1rem" }}>
          <h3>Answer:</h3>
          <p>{answerData.answer}</p>
          <h4>Citations:</h4>
          {answerData.citations.map((c, i) => (
            <div key={i} className="citation">
              <strong>{c.title}</strong> (Page {c.page}) - Score: {c.score}
              <p>{c.snippet}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
