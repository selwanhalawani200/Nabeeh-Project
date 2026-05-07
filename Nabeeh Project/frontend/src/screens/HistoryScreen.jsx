import { useEffect, useState } from "react";
import { fetchHistory } from "../services/api";

export default function HistoryScreen() {
  const [historyData, setHistoryData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadHistory = async () => {
      try {
        setLoading(true);
        setError("");
        const data = await fetchHistory();
        setHistoryData(data);
      } catch (err) {
        setError(err.message || "Failed to load history");
      } finally {
        setLoading(false);
      }
    };

    loadHistory();
  }, []);

  return (
    <div className="screen">
      <h1 className="page-title">History</h1>
      <p className="page-subtitle">Past analyzed calls</p>

      {loading && <div className="card">Loading history...</div>}
      {error && <div className="error-box">Error: {error}</div>}

      {!loading && !error && historyData.length === 0 && (
        <div className="card">No history yet.</div>
      )}

      {!loading && !error && historyData.length > 0 && (
        <div className="card">
          {historyData.map((item, index) => (
            <div className="history-item" key={index}>
              <div className="history-left">
                <div className="history-avatar">👤</div>
                <div>
                  <p className="history-number">{item.file_name}</p>
                  <p className="history-time">{item.created_at}</p>
                </div>
              </div>

              <span
                className={`badge ${
                  String(item.final_label).toUpperCase() === "SAFE"
                    ? "green"
                    : "red"
                }`}
              >
                {item.final_label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}