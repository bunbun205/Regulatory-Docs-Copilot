import { useState } from "react";
import { client, getApiKey } from "../api";

export default function SearchView() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const { data } = await client.POST("/v1/search", {
      headers: { "X-API-Key": getApiKey() || "" },
      body: { query: query, top_k: 5 }
    });
    setLoading(false);
    if (data) setResults(data.results);
  };

  return (
    <div>
      <h2>Vector Search</h2>
      <form onSubmit={handleSearch}>
        <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search query..." />
        <button type="submit">Search</button>
      </form>

      {loading && <div className="loading">Searching...</div>}
      {results.map((hit, i) => (
        <div key={i} style={{ marginTop: "1rem" }}>
          <strong>{hit.title}</strong> (Score: {hit.score.toFixed(4)})
          <pre>{hit.text}</pre>
        </div>
      ))}
    </div>
  );
}
