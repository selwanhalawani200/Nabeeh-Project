import { useLocation, useNavigate } from "react-router-dom";

export default function WarningScreen() {
  const location = useLocation();
  const navigate = useNavigate();

  const result = location.state?.result;
  const transcript = location.state?.transcript || "";

  return (
    <div className="screen dark-screen">
      <div className="warning-banner">
        <span>⚠️</span>
        <span>Fraudulent Call Warning</span>
      </div>

      <div className="warning-card">
        <div className="warning-icon">🚨</div>
        <h2>High fraud risk detected</h2>
        <p>This call appears suspicious based on real-time analysis.</p>

        {result && (
          <>
            <div className="result-item">
              <span className="result-label">Final Label</span>
              <span className="badge red">{result.final_label}</span>
            </div>

            <div className="result-item">
              <span className="result-label">Risk Level</span>
              <span className="result-value">{result.risk_level}</span>
            </div>

            <div className="result-item">
              <span className="result-label">Risk Score</span>
              <span className="result-value">{result.risk_score}</span>
            </div>

            {transcript && (
              <div className="card" style={{ marginTop: 16, textAlign: "left" }}>
                <h3 className="card-title">Transcript</h3>
                <p className="transcript-text">{transcript}</p>
              </div>
            )}
          </>
        )}

        <button className="primary-btn full-btn" onClick={() => navigate("/thank-you")}>
          Continue
        </button>
      </div>
    </div>
  );
}