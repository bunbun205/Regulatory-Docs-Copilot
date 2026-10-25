import { useState } from "react";
import { client, getApiKey } from "../api";

export default function AgentView() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const { data } = await client.POST("/v1/agent/run", {
      headers: { "X-API-Key": getApiKey() || "" },
      body: { query }
    });
    setLoading(false);
    if (data) setResult(data);
  };

  return (
    <div>
      <h2>Agent Run</h2>
      <form onSubmit={handleRun}>
        <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Query for agent..." />
        <button type="submit">Run Agent</button>
      </form>

      {loading && <div className="loading">Agent is working (max 5 steps)...</div>}
      
      {result && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem", marginTop: "1rem" }}>
          <div>
            <h3>Final Answer</h3>
            <p>{result.answer}</p>
            <h3>Citations</h3>
            {result.citations.map((c: any, i: number) => (
               <div key={i} className="citation">{c.title} (Page {c.page})</div>
            ))}
          </div>
          <div>
            <h3>Execution Trace</h3>
            {result.trace.map((step: any) => (
              <div key={step.step} className="trace-step">
                <strong>Step {step.step}: {step.tool}</strong>
                <pre>{JSON.stringify(step.arguments, null, 2)}</pre>
                <div style={{ fontSize: "0.8rem", color: "#666" }}>Result: {step.result_summary} ({step.latency_ms} ms)</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
