from pathlib import Path
import shutil
import uuid
import threading

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from fraud_engine import (
    load_models,
    run_file_realtime_pipeline,
    run_microphone_realtime_pipeline,
    get_mic_live_state,
    reset_mic_live_state,
)

from history_store import (
    save_history_item,
    create_history_item,
    load_history,
)

app = FastAPI(title="Arabic Fraud Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later restrict this to frontend URL only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}

asr_model = None
tokenizer = None
classifier = None
mic_thread = None


@app.on_event("startup")
def startup_event():
    global asr_model, tokenizer, classifier
    asr_model, tokenizer, classifier = load_models()


@app.get("/")
def root():
    return {"message": "Fraud Detection API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "API is running"}

 
@app.get("/history")
def get_history():
    return {"items": load_history()}


@app.post("/predict-audio")
async def predict_audio(file: UploadFile = File(...)):
    global asr_model, tokenizer, classifier

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    suffix = Path(file.filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )

    temp_filename = f"{uuid.uuid4()}{suffix}"
    temp_path = UPLOAD_DIR / temp_filename

    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if asr_model is None or tokenizer is None or classifier is None:
            raise HTTPException(
                status_code=503,
                detail="Models are not loaded yet."
            )

        result = run_file_realtime_pipeline(
            audio_path=str(temp_path),
            asr_model=asr_model,
            tokenizer=tokenizer,
            classifier=classifier
        )

        if result is None:
            raise HTTPException(
                status_code=500,
                detail="Pipeline returned no result. Make sure run_file_realtime_pipeline returns a dictionary."
            )

        call_result = result.get("call_result", {})
        all_segment_results = result.get("all_segment_results", [])
        total_time = result.get("total_time", 0.0)
        final_lexicon_cues = result.get("final_lexicon_cues", [])

        top_segments = sorted(
            all_segment_results,
            key=lambda x: float(x.get("fraud_prob", 0.0)),
            reverse=True
        )[:5]

        transcript = " ".join(
            str(seg.get("text", "")).strip()
            for seg in all_segment_results
            if seg.get("text")
        ).strip()

        safe_top_segments = []
        for seg in top_segments:
            safe_top_segments.append({
                "chunk_id": int(seg.get("chunk_id", 0)),
                "segment_id": int(seg.get("segment_id", 0)),
                "text": str(seg.get("text", "")),
                "highlighted_text": str(seg.get("highlighted_text", "")),
                "lexicon_cues": seg.get("lexicon_cues", []),
                "label": str(seg.get("label", "")),
                "fraud_prob": float(seg.get("fraud_prob", 0.0)),
                "safe_prob": float(seg.get("safe_prob", 0.0)),
            })

        response_data = {
            "status": "success",
            "file_name": str(file.filename),
            "final_label": str(call_result.get("final_label", "")),
            "risk_score": float(call_result.get("risk_score", 0.0)),
            "risk_level": str(call_result.get("risk_level", "")),
            "processing_time_sec": float(total_time or 0.0),
            "transcript": transcript,
            "top_segments": safe_top_segments,
            "final_lexicon_cues": final_lexicon_cues,
            "all_segments_count": int(len(all_segment_results)),
        }

        # Save file analysis result to history
        history_item = create_history_item(
            file_name=str(file.filename),
            final_label=str(call_result.get("final_label", "")),
            risk_level=str(call_result.get("risk_level", "")),
            risk_score=float(call_result.get("risk_score", 0.0)),
            transcript=transcript,
            final_lexicon_cues=final_lexicon_cues
        )
        save_history_item(history_item)

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def mic_detection_worker():
    """
    Run microphone realtime detection in a background thread,
    then save final result to history.
    """
    state = get_mic_live_state()

    try:
        result = run_microphone_realtime_pipeline(
            asr_model=asr_model,
            tokenizer=tokenizer,
            classifier=classifier
        )

        # If the function returns a dictionary, use it
        if isinstance(result, dict):
            final_label = str(result.get("final_label", state.get("final_label", "")))
            risk_level = str(result.get("risk_level", state.get("risk_level", "")))
            risk_score = float(result.get("risk_score", state.get("risk_score", 0.0)))
            transcript = str(result.get("transcript", state.get("transcript", "")))
            final_lexicon_cues = result.get("final_lexicon_cues", state.get("final_lexicon_cues", []))
        else:
            # Otherwise fallback to live state
            final_label = str(state.get("final_label", ""))
            risk_level = str(state.get("risk_level", ""))
            risk_score = float(state.get("risk_score", 0.0))
            transcript = str(state.get("transcript", ""))
            final_lexicon_cues = state.get("final_lexicon_cues", [])

        # Save realtime analysis result to history
        history_item = create_history_item(
            file_name="Live Detection",
            final_label=final_label,
            risk_level=risk_level,
            risk_score=risk_score,
            transcript=transcript,
            final_lexicon_cues=final_lexicon_cues
        )
        save_history_item(history_item)

    except Exception as e:
        state["error"] = str(e)
        state["status"] = "Error"
        state["running"] = False


@app.post("/start-mic-detection")
def start_mic_detection():
    global mic_thread

    state = get_mic_live_state()

    if state["running"]:
        return {
            "status": "already_running",
            "message": "Microphone detection is already running."
        }

    if asr_model is None or tokenizer is None or classifier is None:
        raise HTTPException(
            status_code=503,
            detail="Models are not loaded yet."
        )

    reset_mic_live_state()

    state = get_mic_live_state()
    state["running"] = True
    state["status"] = "Starting microphone detection..."

    mic_thread = threading.Thread(
        target=mic_detection_worker,
        daemon=True
    )
    mic_thread.start()

    return {
        "status": "started",
        "message": "Microphone detection started."
    }


@app.get("/mic-status")
def mic_status():
    return get_mic_live_state()


@app.post("/stop-mic-detection")
def stop_mic_detection():
    state = get_mic_live_state()
    state["running"] = False
    state["status"] = "Stopped"

    return {
        "status": "stopped",
        "message": "Microphone detection stop requested."
    }
