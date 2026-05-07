export default function PermissionCard({ label, sub, enabled = false }) {
  return (
    <div className="permission-row">
      <div className="permission-left">
        <div className="permission-label">{label}</div>
        <div className="permission-sub">{sub}</div>
      </div>
      <div className={`switch ${enabled ? "on" : ""}`}></div>
    </div>
  );
}