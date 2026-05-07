import { useNavigate } from "react-router-dom";

export default function HomeScreen() {
  const navigate = useNavigate();

  return (
    <div className="screen">
      <h1 className="page-title">Welcome 👋</h1>
      <p className="page-subtitle">
        Real-time fraud detection system is active and ready.
      </p>

      <div className="card">
        <div className="card-row">
          <div>
            <h3 className="card-title">Real-Time Fraud Detection</h3>
            <p className="card-sub">System protection is enabled</p>
          </div>
          <span className="badge green">ON</span>
        </div>
      </div>

      <div className="card">
        <h3 className="card-title">Quick Access</h3>

        <button
          className="primary-btn full-btn"
          onClick={() => navigate("/history")}
        >
          Open History
        </button>

        <button
          className="primary-btn full-btn secondary-btn"
          onClick={() => navigate("/realtime")}
        >
          Start Real-Time Analyze
        </button>
      </div>
    </div>
  );
}