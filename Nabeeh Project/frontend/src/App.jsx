import { Routes, Route } from "react-router-dom";
import PhoneFrame from "./components/PhoneFrame";
import HomeScreen from "./screens/HomeScreen";
import HistoryScreen from "./screens/HistoryScreen";
import RealtimeScreen from "./screens/RealtimeScreen";
import WarningScreen from "./screens/WarningScreen";
import ThankYouScreen from "./screens/ThankYouScreen";

export default function App() {
  return (
    <PhoneFrame>
      <Routes>
        <Route path="/" element={<HomeScreen />} />
        <Route path="/history" element={<HistoryScreen />} />
        <Route path="/realtime" element={<RealtimeScreen />} />
        <Route path="/warning" element={<WarningScreen />} />
        <Route path="/thank-you" element={<ThankYouScreen />} />
      </Routes>
    </PhoneFrame>
  );
}