export default function PhoneFrame({ children }) {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "#ececec",
      }}
    >
      <div
        style={{
          width: 430,          // 👈 أكبر
          height: 900,         // 👈 أطول شوي
          background: "#fff",
          border: "10px solid #111",
          borderRadius: 36,
          padding: "40px 16px", // 👈 أقل → مساحة أكبر
          overflowY: "auto",
        }}
      >
        {children}
      </div>
    </div>
  );
}