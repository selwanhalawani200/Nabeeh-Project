export default function AlertBanner({ text = "High fraud risk detected!" }) {
  return (
    <div className="danger-banner">
      <span>⚠️</span>
      <span>{text}</span>
    </div>
  );
}