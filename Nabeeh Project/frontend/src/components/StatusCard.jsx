export default function StatusCard({ title, value, badgeText, badgeColor = "green" }) {
  return (
    <div className="soft-card status-card">
      <div className="status-left">
        <div className="status-title">{title}</div>
        <div className="status-value">{value}</div>
      </div>
      <div className={`pill ${badgeColor}`}>{badgeText}</div>
    </div>
  );
}