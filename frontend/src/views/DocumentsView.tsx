import { useState, useEffect } from "react";
import { client, getApiKey } from "../api";

export default function DocumentsView() {
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 上传表单状态
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [sourceAgency, setSourceAgency] = useState("");
  const [docType, setDocType] = useState("guidance");
  const [year, setYear] = useState(new Date().getFullYear());
  const [version, setVersion] = useState("v1");
  const [uploadJobId, setUploadJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);

  const fetchDocuments = async () => {
    setLoading(true);
    setError("");
    const { data, error } = await client.GET("/v1/documents", {
      headers: { "X-API-Key": getApiKey() || "" }
    });
    setLoading(false);
    if (error) {
      // Cast to any to bypass strict type check for the generic error envelope
      setError((error as any).error?.message || "Failed to load documents");
    } else if (data) {
      setDocuments(data.items);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  // 轮询 Job 状态
  useEffect(() => {
    if (!uploadJobId || jobStatus === "completed" || jobStatus === "failed") return;

    const interval = setInterval(async () => {
      const { data } = await client.GET("/v1/jobs/{job_id}", {
        params: { path: { job_id: uploadJobId } },
        headers: { "X-API-Key": getApiKey() || "" }
      });

      if (data) {
        setJobStatus(data.status);
        if (data.status === "completed" || data.status === "failed") {
          fetchDocuments(); // 刷新文档列表
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [uploadJobId, jobStatus]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError("");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", title);
    formData.append("source_agency", sourceAgency);
    formData.append("doc_type", docType);
    formData.append("year", year.toString());
    formData.append("version", version);

    try {
      const response = await fetch("/api/v1/documents", {
        method: "POST",
        headers: { "X-API-Key": getApiKey() || "" },
        body: formData,
      });

      const resData = await response.json();
      if (!response.ok) {
        setError(resData.error?.message || "Upload failed");
      } else {
        setUploadJobId(resData.job_id);
        setJobStatus("queued");
      }
    } catch (err: any) {
      setError("Network error during upload");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <section>
        <h2>Upload Document</h2>
        <form onSubmit={handleUpload} style={{ border: "1px solid #ddd", padding: "1rem" }}>
          <div className="form-group">
            <label>File:</label>
            <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} required />
          </div>
          <div className="form-group">
            <label>Title:</label>
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Source Agency:</label>
            <input type="text" value={sourceAgency} onChange={(e) => setSourceAgency(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Doc Type:</label>
            <select value={docType} onChange={(e) => setDocType(e.target.value)}>
              <option value="guidance">Guidance</option>
              <option value="regulation">Regulation</option>
              <option value="policy">Policy</option>
            </select>
          </div>
          <div className="form-group">
            <label>Year:</label>
            <input type="number" value={year} onChange={(e) => setYear(parseInt(e.target.value))} required />
          </div>
          <div className="form-group">
            <label>Version:</label>
            <input type="text" value={version} onChange={(e) => setVersion(e.target.value)} required />
          </div>
          <button type="submit">Upload Document</button>
        </form>

        {uploadJobId && (
          <div style={{ marginTop: "1rem" }}>
            Job Status: <strong>{jobStatus}</strong> ({uploadJobId})
          </div>
        )}
      </section>

      <section>
        <h2>Document Library</h2>
        {error && <div className="error">{error}</div>}
        {loading ? (
          <div className="loading">Loading documents...</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Agency</th>
                <th>Type</th>
                <th>Year</th>
                <th>Version</th>
                <th>File</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.title}</td>
                  <td>{doc.source_agency}</td>
                  <td>{doc.doc_type}</td>
                  <td>{doc.year}</td>
                  <td>{doc.version}</td>
                  <td>{doc.filename}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
