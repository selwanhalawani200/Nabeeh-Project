import { useNavigate } from "react-router-dom";

export default function ThankYouScreen() {
  const navigate = useNavigate();

  return (
    <div className="screen dark-screen">
      <div className="thank-you-box">
        <h1>Thank you!</h1>
        <button className="primary-btn" onClick={() => navigate("/")}>
          Back to Home
        </button>
      </div>
    </div>
  );
}