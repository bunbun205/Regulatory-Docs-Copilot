import { useState, useEffect } from "react";
import { client, getApiKey } from "../api";

export default function GapCheckView() {
  const [text, setText] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [report, setReport] = useState<any>(null);

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    setReport(null);
    const formData = new FormData();
    formData.append("text", text);

    const response = await fetch("/api/v1/gapcheck", {
      method: "POST",
      headers: { "X-API-Key": getApiKey() || "" },
      body: formData,
    });
    const data = await response.json();
    if (response.ok) {
      setJobId(data.job_id);
      setJobStatus("queued");
    }
  };

  useEffect(() => {
    if (!jobId || jobStatus === "completed" || jobStatus === "failed" || jobStatus === "cancelled") return;

    const interval = setInterval(async () => {
      const { data } = await client.GET("/v1/gapcheck/{job_id}", {
        params: { path: { job_id: jobId } },
        headers: { "X-API-Key": getApiKey() || "" }
      });

      if (data) {
        setJobStatus(data.status);
        if (data.status === "completed" && data.report) {
          setReport(data.report);
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, jobStatus]);

  return (
    <div>
      <h2>Compliance Gap Checker</h2>
      <form onSubmit={handleStart}>
        <textarea
          rows={10}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste SOP Content here..."
        />
        <button type="submit">Run Gap Check</button>
      </form>

      {jobId && <div>Job ID: {jobId} | Status: {jobStatus}</div>}

      {report && (
        <div style={{ marginTop: "2rem" }}>
          <h3>Findings Report</h3>
          <div className="banner">{report.banner}</div>

          {report.findings.map((finding: any) => (
            <div key={finding.finding_id} className={`finding severity-${finding.severity}`}>
              <h4>[{finding.finding_id}] {finding.verdict.toUpperCase()} (Severity: {finding.severity})</h4>
              <p><strong>Rationale:</strong> {finding.rationale}</p>
              <p><strong>Suggested Fix:</strong> {finding.suggested_fix}</p>
              <div>
                <strong>Regulation Citations:</strong>
                {finding.regulation_citations.map((c: any, i: number) => (
                  <div key={i} className="citation">{c.title} - Page {c.page}</div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
