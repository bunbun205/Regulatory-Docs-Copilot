import { useState } from "react";
import { getApiKey, setApiKey } from "./api";

// 导入各个视图组件
import DocumentsView from "./views/DocumentsView";
import SearchView from "./views/SearchView";
import AskView from "./views/AskView";
import AgentView from "./views/AgentView";
import GapCheckView from "./views/GapCheckView";

export default function App() {
  const [apiKey, setApiKeyState] = useState<string>(() => getApiKey() || "");
  const [savedKey, setSavedKey] = useState<string>(() => getApiKey() || "");
  const [activeTab, setActiveTab] = useState<string>("documents");

  const handleSaveKey = () => {
    const key = apiKey.trim();
    setApiKey(key);
    setSavedKey(key);
  };

  return (
    <div>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <h1>Regulatory Docs Copilot</h1>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input
            type="password"
            aria-label="API key"
            placeholder="Enter API Key"
            value={apiKey}
            onChange={(e) => setApiKeyState(e.target.value)}
          />
          <button onClick={handleSaveKey}>Save Key</button>
        </div>
      </header>

      <nav>
        <button className={activeTab === "documents" ? "active" : ""} onClick={() => setActiveTab("documents")}>Documents & Upload</button>
        <button className={activeTab === "search" ? "active" : ""} onClick={() => setActiveTab("search")}>Search</button>
        <button className={activeTab === "ask" ? "active" : ""} onClick={() => setActiveTab("ask")}>Ask (RAG)</button>
        <button className={activeTab === "agent" ? "active" : ""} onClick={() => setActiveTab("agent")}>Agent</button>
        <button className={activeTab === "gapcheck" ? "active" : ""} onClick={() => setActiveTab("gapcheck")}>Gap Check</button>
      </nav>

      <main>
        {!savedKey ? (
          <div className="error">Please set a valid API Key to use the application.</div>
        ) : (
          <div key={savedKey}>
            {activeTab === "documents" && <DocumentsView />}
            {activeTab === "search" && <SearchView />}
            {activeTab === "ask" && <AskView />}
            {activeTab === "agent" && <AgentView />}
            {activeTab === "gapcheck" && <GapCheckView />}
          </div>
        )}
      </main>
    </div>
  );
}
