import { useEffect, useState } from "react";
import {
  ChevronLeft,
  MoreVertical,
  Mic,
  Clock3,
  ShieldCheck,
  BarChart3,
  Gauge,
  Square,
  Info,
} from "lucide-react";
import {
  startMicDetection,
  fetchMicStatus,
  stopMicDetection,
} from "../services/api";

export default function RealtimeScreen() {
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState("Tap the microphone to start");
  const [liveLabel, setLiveLabel] = useState("SAFE");
  const [liveRisk, setLiveRisk] = useState("LOW");
  const [liveScore, setLiveScore] = useState(0);
  const [explainability, setExplainability] = useState(null);
  const [allExplainability, setAllExplainability] = useState([]);
  const [seconds, setSeconds] = useState(0);

  const getExplainability = (data) => {
    if (data.latest_lexicon_cues && data.latest_lexicon_cues.length > 0) {
      return data.latest_lexicon_cues;
    }

    if (data.final_lexicon_cues && data.final_lexicon_cues.length > 0) {
      return data.final_lexicon_cues;
    }

    return (
      data.explainability ||
      data.explanation ||
      data.explainable_reason ||
      data.reason ||
      data.reasons ||
      data.top_keywords ||
      data.keywords ||
      data.shap_explanation ||
      null
    );
  };

  const formatExplainability = (value) => {
    if (!value) return "";

    if (typeof value === "string") return value;

    if (Array.isArray(value)) {
      return value
        .map((item) => {
          if (typeof item === "string") return item;
          return `${item.keyword} (${item.type}) x${item.count}`;
        })
        .join("\n");
    }

    if (typeof value === "object") {
      return JSON.stringify(value, null, 2);
    }

    return String(value);
  };

  const handleStart = async () => {
    if (isRunning) return;

    try {
      setStatus("Starting...");
      setLiveLabel("SAFE");
      setLiveRisk("LOW");
      setLiveScore(0);
      setExplainability(null);
      setAllExplainability([]);
      setSeconds(0);

      await startMicDetection();
      setIsRunning(true);
      setStatus("Listening...");
    } catch (err) {
      console.error(err);
      setStatus("Error starting mic");
    }
  };

  useEffect(() => {
    if (!isRunning) return;

    const timer = setInterval(() => {
      setSeconds((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [isRunning]);

  useEffect(() => {
    if (!isRunning) return;

    const interval = setInterval(async () => {
      try {
        const data = await fetchMicStatus();

        console.log("Mic status response:", data);

        setStatus(data.status || "Running...");
        setLiveLabel(data.final_label || "SAFE");
        setLiveRisk(data.risk_level || "LOW");
        setLiveScore(
          data.risk_score !== undefined && data.risk_score !== null
            ? Number(data.risk_score)
            : 0
        );

       const newExplainability = getExplainability(data);

if (newExplainability) {
  const newItems = Array.isArray(newExplainability)
    ? newExplainability
    : [newExplainability];

  setAllExplainability((prev) => {
    const combined = [...prev, ...newItems];

    const unique = combined.filter((item, index, self) => {
      if (typeof item === "string") {
        return self.indexOf(item) === index;
      }

      return (
        index ===
        self.findIndex(
          (x) =>
            x.keyword === item.keyword &&
            x.type === item.type
        )
      );
    });

    setExplainability(unique);
    return unique;
  });
}

        if (!data.running && data.final_label) {
          setIsRunning(false);
          setStatus("Analysis completed");
        }
      } catch (err) {
        console.error(err);
        setStatus("Connection error");
        setIsRunning(false);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isRunning]);

  const handleStop = async () => {
    try {
      await stopMicDetection();
      setIsRunning(false);
      setStatus("Stopped");
    } catch (err) {
      console.error(err);
      setStatus("Error stopping mic");
    }
  };

  const formatTime = (totalSeconds) => {
    const hrs = String(Math.floor(totalSeconds / 3600)).padStart(2, "0");
    const mins = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, "0");
    const secs = String(totalSeconds % 60).padStart(2, "0");
    return `${hrs}:${mins}:${secs}`;
  };

  const waveformHeights = [
    10, 12, 16, 22, 34, 18, 14, 20, 38, 18, 14, 16, 18, 30, 22, 20, 16, 28,
    18, 12, 10,
  ];

  const waveformColors = [
    "#ef4444",
    "#f97316",
    "#fb923c",
    "#f59e0b",
    "#eab308",
    "#facc15",
    "#84cc16",
    "#4ade80",
    "#22c55e",
    "#14b8a6",
    "#2dd4bf",
    "#06b6d4",
    "#38bdf8",
    "#3b82f6",
    "#60a5fa",
    "#6366f1",
    "#8b5cf6",
    "#9333ea",
    "#a855f7",
    "#c084fc",
    "#9333ea",
  ];

  const labelIsFraud = liveLabel === "FRAUD";

  return (
    <div className="rt-page">
      <div className="rt-topbar">
        <button className="rt-icon-btn">
          <ChevronLeft size={28} strokeWidth={2.5} />
        </button>

        <button className="rt-icon-btn">
          <MoreVertical size={26} strokeWidth={2.5} />
        </button>
      </div>

      <h1 className="rt-title">Real-Time Detection</h1>
      <p className="rt-subtitle">Live fraud detection using microphone</p>

      <div className="rt-main-card">
        <div className="rt-mic-section">
          <div className={`rt-mic-outer ${isRunning ? "listening" : ""}`}>
            <button
              className="rt-mic-inner"
              onClick={handleStart}
              disabled={isRunning}
            >
              <Mic size={96} strokeWidth={2} className="rt-mic-icon" />
            </button>
          </div>

          <div className="rt-status-text">{status}</div>

          <div className="rt-waveform">
            {waveformHeights.map((h, i) => (
              <span
                key={i}
                className={`rt-wave-bar ${isRunning ? "active" : ""}`}
                style={{
                  height: `${h}px`,
                  backgroundColor: waveformColors[i],
                  animationDelay: `${i * 0.06}s`,
                }}
              />
            ))}
          </div>

          <div className="rt-timer-row">
            <Clock3 size={28} />
            <span>{formatTime(seconds)}</span>
          </div>
        </div>

        <div className="rt-analysis-card">
          <div className="rt-card-header">
            <span className="rt-green-dot"></span>
            <h3>Live Analysis</h3>
          </div>

          <div className="rt-analysis-row">
            <div className="rt-analysis-left">
              <div className="rt-analysis-icon rt-green-bg">
                <ShieldCheck size={24} />
              </div>
              <div>
                <p className="rt-analysis-label">Current Label</p>
                <p
                  className={`rt-analysis-value ${
                    labelIsFraud ? "rt-red-text" : "rt-green-text"
                  }`}
                >
                  {liveLabel}
                </p>
              </div>
            </div>

            <span className={`rt-pill ${labelIsFraud ? "rt-pill-red" : "rt-pill-green"}`}>
              {liveLabel}
            </span>
          </div>

          <div className="rt-analysis-row">
            <div className="rt-analysis-left">
              <div className="rt-analysis-icon rt-blue-bg">
                <BarChart3 size={24} />
              </div>
              <div>
                <p className="rt-analysis-label">Risk Level</p>
                <p className="rt-analysis-value rt-blue-text">{liveRisk}</p>
              </div>
            </div>

            <span className="rt-pill rt-pill-blue">{liveRisk}</span>
          </div>

          <div className="rt-analysis-row rt-analysis-row-last">
            <div className="rt-analysis-left">
              <div className="rt-analysis-icon rt-purple-bg">
                <Gauge size={24} />
              </div>
              <div>
                <p className="rt-analysis-label">Risk Score</p>
                <p className="rt-analysis-value rt-purple-text">
                  {(liveScore * 100).toFixed(1)}%
                </p>
              </div>
            </div>

            <div className="rt-score-track">
              <div
                className="rt-score-fill"
                style={{ width: `${Math.min(liveScore * 100, 100)}%` }}
              />
            </div>
          </div>
        </div>

        {explainability && (
          <div className="rt-analysis-card">
            <div className="rt-card-header">
              <span className="rt-green-dot"></span>
              <h3>Explainability</h3>
            </div>

            <div className="rt-analysis-row rt-analysis-row-last">
              <div className="rt-analysis-left">
                <div className="rt-analysis-icon rt-blue-bg">
                  <Info size={24} />
                </div>

                <div>
                  <p className="rt-analysis-label">Why this result?</p>

                  <pre
                    className="rt-analysis-value rt-blue-text"
                    style={{
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                      margin: 0,
                      fontFamily: "inherit",
                      fontSize: "0.75rem",
                      maxHeight: "100px",
                      overflowY: "auto",
                      paddingRight: "4px",
                      background: "#f8f9fa",
                      borderRadius: "8px",
                      padding: "6px",
                    }}
                  >
                    {formatExplainability(explainability)}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}

        {isRunning ? (
          <button className="rt-stop-btn" onClick={handleStop}>
            <Square size={22} fill="white" stroke="white" />
            <span>Stop Detection</span>
          </button>
        ) : (
          <button className="rt-start-btn" onClick={handleStart}>
            Start Detection
          </button>
        )}
      </div>
    </div>
  );
}