import { Link, useLocation } from "react-router-dom";

export default function BottomNav() {
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  return (
    <div className="bottom-nav">
      <Link to="/home" className={`nav-item ${isActive("/home") ? "active" : ""}`}>
        <span>⌂</span>
        <span>Home</span>
      </Link>

      <Link to="/history" className={`nav-item ${isActive("/history") ? "active" : ""}`}>
        <span>📄</span>
        <span>Reports</span>
      </Link>

      <Link to="/analyze" className={`nav-item ${isActive("/analyze") ? "active" : ""}`}>
        <span>🛡️</span>
        <span>Protection</span>
      </Link>
    </div>
  );
}