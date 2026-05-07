import os
import re
import time
import queue
import threading
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
import torch
import sounddevice as sd
from pathlib import Path

from transformers import AutoTokenizer, AutoModelForSequenceClassification


# ============================================
# CONFIGURATION
# ============================================

WHISPER_SIZE = "small"
MODEL_PATH = r"C:\Users\Batoo\Downloads\project\project\project\model\MARBERT_final"
print("[DEBUG] MODEL_PATH =", MODEL_PATH)
print("[DEBUG] EXISTS =", Path(MODEL_PATH).exists())
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

LANGUAGE = "ar"
SAMPLE_RATE = 16000

CHUNK_DURATION = 6
OVERLAP_DURATION = 0.2
STEP_DURATION = CHUNK_DURATION - OVERLAP_DURATION

if OVERLAP_DURATION >= CHUNK_DURATION:
    raise ValueError("OVERLAP_DURATION must be smaller than CHUNK_DURATION")

CONFIDENCE_THRESHOLD = 0.70

FRAUD_INDEX = 0
SAFE_INDEX = 1

SILENCE_RMS_THRESHOLD = 0.002
MIN_NON_SILENT_RATIO = 0.05


# ============================================
# GLOBAL LIVE STATE FOR MICROPHONE MODE
# ============================================

mic_live_state = {
    "running": False,
    "status": "idle",
    "transcript": "",
    "final_label": "SAFE",
    "risk_score": 0.0,
    "risk_level": "LOW",
    "max_fraud_prob": 0.0,
    "avg_fraud_prob": 0.0,
    "chunk_id": 0,
    "error": "",
    "final_lexicon_cues": [],
    "latest_lexicon_cues": []
}


def reset_mic_live_state():
    mic_live_state["running"] = False
    mic_live_state["status"] = "idle"
    mic_live_state["transcript"] = ""
    mic_live_state["final_label"] = "SAFE"
    mic_live_state["risk_score"] = 0.0
    mic_live_state["risk_level"] = "LOW"
    mic_live_state["max_fraud_prob"] = 0.0
    mic_live_state["avg_fraud_prob"] = 0.0
    mic_live_state["chunk_id"] = 0
    mic_live_state["error"] = ""
    mic_live_state["final_lexicon_cues"] = []
    mic_live_state["latest_lexicon_cues"] = []


def get_mic_live_state():
    return mic_live_state


# ============================================
# MODEL LOADING
# ============================================

def load_models():
    print(f"[INFO] Loading Faster-Whisper ({WHISPER_SIZE})...")
    compute_type = "int8" if DEVICE == "cpu" else "float16"
    asr_model = WhisperModel(WHISPER_SIZE, device=DEVICE, compute_type=compute_type)

    print(f"[INFO] Loading MARBERT from: {MODEL_PATH}")
    tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    local_files_only=True,
    use_fast=False
    )
    classifier = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH, local_files_only=True)
    classifier.to(DEVICE)
    classifier.eval()

    print(f"[INFO] Running on: {DEVICE}")
    return asr_model, tokenizer, classifier


# ============================================
# TEXT CLEANING + SEGMENTATION
# ============================================

def clean_arabic_text(text):
    if not text:
        return ""

    text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)
    text = re.sub(r'[^\u0600-\u06FF0-9\s\.\,\!\?\;\:\،\؟]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def split_text_into_segments(text, max_words=30):
    text = clean_arabic_text(text)

    if not text:
        return []

    parts = re.split(r'[\.!\?,;:\،\؟]+', text)
    parts = [p.strip() for p in parts if p.strip()]

    segments = []
    for part in parts:
        words = part.split()

        if len(words) <= max_words:
            segments.append(part)
        else:
            for i in range(0, len(words), max_words):
                chunk_words = words[i:i + max_words]
                segments.append(" ".join(chunk_words))

    return [seg for seg in segments if seg.strip()]


# ============================================
# SILENCE DETECTION
# ============================================

def is_silent_chunk(audio, rms_threshold=SILENCE_RMS_THRESHOLD, min_non_silent_ratio=MIN_NON_SILENT_RATIO):
    if len(audio) == 0:
        return True

    frame_size = int(0.02 * SAMPLE_RATE)
    hop_size = frame_size

    if frame_size <= 0:
        return True

    rms_values = []

    for i in range(0, len(audio), hop_size):
        frame = audio[i:i + frame_size]

        if len(frame) == 0:
            continue

        rms = np.sqrt(np.mean(frame ** 2))
        rms_values.append(rms)

    if not rms_values:
        return True

    non_silent_frames = sum(r > rms_threshold for r in rms_values)
    non_silent_ratio = non_silent_frames / len(rms_values)

    return non_silent_ratio < min_non_silent_ratio


# ============================================
# AUDIO HELPERS
# ============================================

def ensure_mono(audio):
    if len(audio.shape) > 1:
        audio = np.mean(audio, axis=1)
    return audio


def resample_audio(audio, orig_sr, target_sr):
    if orig_sr == target_sr:
        return audio.astype(np.float32)

    duration = len(audio) / orig_sr
    old_times = np.linspace(0, duration, num=len(audio), endpoint=False)
    new_length = int(duration * target_sr)
    new_times = np.linspace(0, duration, num=new_length, endpoint=False)

    resampled = np.interp(new_times, old_times, audio).astype(np.float32)
    return resampled


def load_audio_file(audio_path):
    audio, sr = sf.read(audio_path)
    audio = ensure_mono(audio)

    if sr != SAMPLE_RATE:
        audio = resample_audio(audio, sr, SAMPLE_RATE)
        sr = SAMPLE_RATE

    return audio.astype(np.float32), sr


def generate_overlapping_chunks(audio, sr, chunk_duration=3, overlap_duration=1):
    chunk_size = int(chunk_duration * sr)
    step_size = int((chunk_duration - overlap_duration) * sr)

    chunks = []
    start = 0
    chunk_id = 1

    while start < len(audio):
        end = start + chunk_size
        chunk_audio = audio[start:end]

        if len(chunk_audio) < chunk_size:
            padding = np.zeros(chunk_size - len(chunk_audio), dtype=np.float32)
            chunk_audio = np.concatenate([chunk_audio, padding])

        start_sec = start / sr
        end_sec = min(end, len(audio)) / sr

        chunks.append({
            "chunk_id": chunk_id,
            "audio": chunk_audio.astype(np.float32),
            "sr": sr,
            "start_sec": start_sec,
            "end_sec": end_sec
        })

        start += step_size
        chunk_id += 1

    return chunks


# ============================================
# ASR
# ============================================

def transcribe_chunk(asr_model, chunk_audio, sr=SAMPLE_RATE):
    if sr != SAMPLE_RATE:
        chunk_audio = resample_audio(chunk_audio, sr, SAMPLE_RATE)

    chunk_audio = chunk_audio.astype(np.float32)

    segments, info = asr_model.transcribe(chunk_audio, language=LANGUAGE)
    text = " ".join([segment.text for segment in segments]).strip()
    return text


# ============================================
# LEXICON-BASED FRAUD CUES (EXPLAINABILITY)
# ============================================

FRAUD_LEXICON = {
    "phishing": [
        "تعطيل", "تم إيقاف", "حسابك", "سيتم إغلاق", "توثيق", "التحقق", "رمز", "رمز التحقق",
        "الرمز", "إعادة تفعيل", "تحديث", "تحديث البيانات", "نحتاج نتحقق", "رسالة", "فتح الحساب",
        "تسجيل الدخول", "معلوماتك", "نؤكد هويتك", "الهوية", "مرفوض", "رفض النظام"
    ],
    "bank_credentials": [
        "بطاقة", "cvv", "رقم البطاقة", "رقم سري", "الرقم السري", "كلمة السر", "تحويل", "سحب", "ايداع",
        "رصيد", "حوالة", "فاتورة", "تفاصيل الحساب", "حساب بنكي", "بيانات البنك"
    ],
    "identity_theft": [
        "رقم الهوية", "بطاقة الأحوال", "رقم الإقامة", "رقم السجل", "إثبات", "اثبات الهوية",
        "نسخة الهوية", "ارسل هويتك"
    ],
    "customer_service": [
        "موظف البنك", "خدمة العملاء", "الدعم الفني", "موظف حكومي", "إدارة البنك", "نحتاج بياناتك",
        "تصحيح البيانات", "لدينا مشكلة", "خطأ في النظام"
    ],
    "investment": [
        "عوائد", "عوائد مضمونة", "نسبة", "استثمار", "استثمر", "أرباح", "ربح سريع", "دخل إضافي",
        "مبلغ بسيط", "بدون خسارة", "مكسب", "عرض خاص", "فرصة ذهبية", "مضمون", "80%"
    ],
    "lottery_prize": [
        "ربحت", "جائزة", "مبروك", "سحب", "فوز", "هدية", "مبلغ مالي", "سحب الجوائز", "الرقم الفائز"
    ],
    "threat": [
        "سيتم ايقاف", "سيتم حظر", "غرامة", "بلاغ", "مخالفة", "تهديد", "شرطة"
    ],
}

kw2type = {}
for cat, kws in FRAUD_LEXICON.items():
    for kw in kws:
        kw2type[kw] = cat

LEXICON_PATTERN = r'(' + '|'.join(map(re.escape, sorted(kw2type.keys(), key=len, reverse=True))) + r')'


def analyze_keywords(text):
    found = []

    def repl(m):
        word = m.group(0)
        found.append(word)
        return f"<<{word}>>"

    marked_text = re.sub(LEXICON_PATTERN, repl, text)

    keyword_counts = {}
    for word in found:
        keyword_counts[word] = keyword_counts.get(word, 0) + 1

    cues = []
    for word, count in keyword_counts.items():
        cues.append({
            "keyword": word,
            "type": kw2type.get(word, "other"),
            "count": count
        })

    return marked_text, cues


def summarize_lexicon_cues(all_segment_results):
    summary = {}

    for seg in all_segment_results:
        for cue in seg.get("lexicon_cues", []):
            key = (cue["keyword"], cue["type"])
            summary[key] = summary.get(key, 0) + cue["count"]

    final_cues = []
    for (keyword, cue_type), count in summary.items():
        final_cues.append({
            "keyword": keyword,
            "type": cue_type,
            "count": count
        })

    final_cues.sort(key=lambda x: (x["type"], -x["count"]))
    return final_cues


# ============================================
# CLASSIFICATION
# ============================================

def predict_text(classifier, tokenizer, text):
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=256
    )

    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

    with torch.no_grad():
        logits = classifier(**inputs).logits
        probs = torch.softmax(logits, dim=1)

    fraud_prob = float(probs[0][FRAUD_INDEX].item())
    safe_prob = float(probs[0][SAFE_INDEX].item())

    label = "FRAUD" if fraud_prob > safe_prob else "SAFE"

    return label, fraud_prob, safe_prob


def predict_segments(classifier, tokenizer, segments, chunk_id):
    results = []

    for seg_idx, segment_text in enumerate(segments, start=1):
        if not segment_text.strip():
            continue

        label, fraud_prob, safe_prob = predict_text(classifier, tokenizer, segment_text)

        marked_text, lexicon_cues = analyze_keywords(segment_text)

        results.append({
             "chunk_id": chunk_id,
             "segment_id": seg_idx,
             "text": segment_text,
             "highlighted_text": marked_text,
             "lexicon_cues": lexicon_cues,
             "label": label,
             "fraud_prob": fraud_prob,
             "safe_prob": safe_prob
         })

    return results


# ============================================
# AGGREGATION
# ============================================

def update_live_decision(all_segment_results):
    if not all_segment_results:
        return [], {
            "final_label": "SAFE",
            "risk_score": 0.0,
            "risk_level": "LOW",
            "max_fraud_prob": 0.0,
            "avg_fraud_prob": 0.0
        }

    fraud_probs = [seg["fraud_prob"] for seg in all_segment_results]

    max_fraud_prob = max(fraud_probs)
    avg_fraud_prob = sum(fraud_probs) / len(fraud_probs)

    risk_score = 0.4 * max_fraud_prob + 0.6 * avg_fraud_prob

    if risk_score < 0.40:
        risk_level = "LOW"
    elif risk_score < 0.70:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    final_label = "FRAUD" if risk_score >= CONFIDENCE_THRESHOLD else "SAFE"

    call_result = {
        "final_label": final_label,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "max_fraud_prob": max_fraud_prob,
        "avg_fraud_prob": avg_fraud_prob
    }

    return all_segment_results, call_result


# ============================================
# DISPLAY
# ============================================

def print_live_update(chunk_info, transcript, segment_results, used_segments, call_result, latency):
    print("\n" + "=" * 60)
    print(f"[LIVE UPDATE] Chunk {chunk_info['chunk_id']}  ({chunk_info['start_sec']:.1f}s -> {chunk_info['end_sec']:.1f}s)")
    print("-" * 60)

    print(f"[TRANSCRIPT] {transcript if transcript else '[EMPTY]'}")

    if segment_results:
        print("\n[SEGMENT PREDICTIONS]")
        for seg in segment_results:
            print(
                f"  - Segment {seg['segment_id']}: "
                f"{seg['label']} | fraud={seg['fraud_prob']:.4f} | safe={seg['safe_prob']:.4f}"
            )
            print(f"    Text: {seg['text']}")
            if seg.get("lexicon_cues"):
                print(f"    Highlighted: {seg['highlighted_text']}")
                print("    Lexicon cues:")
                for cue in seg["lexicon_cues"]:
                    print(
                        f"      - {cue['keyword']} | type={cue['type']} | count={cue['count']}"
                    )
    else:
        print("\n[SEGMENT PREDICTIONS] No valid segments.")

    print("\n[ALL SEGMENTS USED IN DECISION]")
    for i, seg in enumerate(used_segments, start=1):
        print(
            f"  {i}. Chunk {seg['chunk_id']} | Segment {seg['segment_id']} "
            f"| fraud={seg['fraud_prob']:.4f} | safe={seg['safe_prob']:.4f} | label={seg['label']}"
        )

    print("\n[CURRENT DECISION]")
    print(f"  FINAL LABEL   : {call_result['final_label']}")
    print(f"  RISK SCORE    : {call_result['risk_score']:.4f}")
    print(f"  RISK LEVEL    : {call_result['risk_level']}")
    print(f"  MAX FRAUD PROB: {call_result['max_fraud_prob']:.4f}")
    print(f"  AVG FRAUD PROB: {call_result['avg_fraud_prob']:.4f}")
    print(f"  Chunk latency : {latency:.2f} sec")
    print("=" * 60)


# ============================================
# FILE MODE (FAKE REAL-TIME)
# ============================================

def run_file_realtime_pipeline(audio_path, asr_model, tokenizer, classifier):
    print("[INFO] Running FAKE real-time mode from audio file...")
    audio, sr = load_audio_file(audio_path)
    chunks = generate_overlapping_chunks(audio, sr, CHUNK_DURATION, OVERLAP_DURATION)

    print(f"[INFO] Total chunks: {len(chunks)}")

    all_segment_results = []
    total_start = time.time()

    call_result = {
        "final_label": "SAFE",
        "risk_score": 0.0,
        "risk_level": "LOW",
        "max_fraud_prob": 0.0,
        "avg_fraud_prob": 0.0
    }

    for chunk in chunks:
        chunk_start = time.time()

        print(f"\n[INFO] Processing chunk {chunk['chunk_id']}...")

        if is_silent_chunk(chunk["audio"]):
            latency = time.time() - chunk_start
            print(f"[INFO] Chunk {chunk['chunk_id']} is mostly silent -> skipped")

            used_segments, call_result = update_live_decision(all_segment_results)

            print_live_update(
                chunk_info=chunk,
                transcript="[SKIPPED - SILENCE]",
                segment_results=[],
                used_segments=used_segments,
                call_result=call_result,
                latency=latency
            )
            continue

        transcript = transcribe_chunk(asr_model, chunk["audio"], chunk["sr"])

        if transcript.strip():
            segments = split_text_into_segments(transcript, max_words=30)
            segment_results = predict_segments(
                classifier, tokenizer, segments, chunk["chunk_id"]
            )
            all_segment_results.extend(segment_results)
        else:
            segment_results = []

        used_segments, call_result = update_live_decision(all_segment_results)

        latency = time.time() - chunk_start

        print_live_update(
            chunk_info=chunk,
            transcript=transcript,
            segment_results=segment_results,
            used_segments=used_segments,
            call_result=call_result,
            latency=latency
        )

    total_time = time.time() - total_start

    final_lexicon_cues = summarize_lexicon_cues(all_segment_results)

    print("\n" + "#" * 60)
    print("FINAL FILE-BASED REAL-TIME DECISION")
    print(f"FINAL LABEL : {call_result['final_label']}")
    print(f"FINAL SCORE : {call_result['risk_score']:.4f}")
    print(f"FINAL RISK  : {call_result['risk_level']}")
    print(f"TOTAL TIME  : {total_time:.2f} sec")

    print("\n[FINAL LEXICON-BASED EXPLANATION]")
    if final_lexicon_cues:
        for cue in final_lexicon_cues:
             print(
              f"  - {cue['keyword']} | type={cue['type']} | count={cue['count']}"
              )
    else:
         print("  No fraud-related lexicon cues detected.")

    print("#" * 60)

    return {
    "call_result": call_result,
    "all_segment_results": all_segment_results,
    "total_time": total_time,
    "final_lexicon_cues": final_lexicon_cues
    }


# ============================================
# MICROPHONE MODE (TRUE REAL-TIME)
# ============================================

audio_queue = queue.Queue()


def mic_callback(indata, frames, time_info, status):
    if status:
        print(f"[MIC WARNING] {status}")
    audio_queue.put(indata.copy())

def run_microphone_realtime_pipeline(asr_model, tokenizer, classifier):
    print("[INFO] Running TRUE real-time mode from microphone...")
    print("[INFO] Speak now. Press Ctrl+C to stop.\n")

    chunk_samples = int(CHUNK_DURATION * SAMPLE_RATE)
    step_samples = int((CHUNK_DURATION - OVERLAP_DURATION) * SAMPLE_RATE)

    buffer_audio = np.array([], dtype=np.float32)
    all_segment_results = []
    chunk_id = 1
    stop_requested = False

    mic_live_state["running"] = True
    mic_live_state["status"] = "Listening..."
    mic_live_state["transcript"] = ""
    mic_live_state["error"] = ""

    call_result = {
        "final_label": "SAFE",
        "risk_score": 0.0,
        "risk_level": "LOW",
        "max_fraud_prob": 0.0,
        "avg_fraud_prob": 0.0
    }

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=mic_callback,
        blocksize=int(0.5 * SAMPLE_RATE)
    )

    total_start = time.time()

    try:
        with stream:
            time.sleep(2)

            while True:
                # stop if endpoint requested stop
                if not mic_live_state["running"] or stop_requested:
                    break

                new_audio = audio_queue.get(timeout=2).flatten().astype(np.float32)
                buffer_audio = np.concatenate([buffer_audio, new_audio])

                while len(buffer_audio) >= chunk_samples:
                    chunk_start = time.time()

                    current_chunk = buffer_audio[:chunk_samples].astype(np.float32)
                    start_sec = (chunk_id - 1) * STEP_DURATION
                    end_sec = start_sec + CHUNK_DURATION

                    chunk_info = {
                        "chunk_id": chunk_id,
                        "audio": current_chunk,
                        "sr": SAMPLE_RATE,
                        "start_sec": start_sec,
                        "end_sec": end_sec
                    }

                    mic_live_state["chunk_id"] = chunk_id
                    mic_live_state["status"] = f"Analyzing chunk {chunk_id}..."

                    if is_silent_chunk(current_chunk):
                        latency = time.time() - chunk_start
                        print(f"[INFO] Chunk {chunk_id} is mostly silent -> skipped")

                        used_segments, call_result = update_live_decision(all_segment_results)

                        mic_live_state["final_label"] = call_result["final_label"]
                        mic_live_state["risk_score"] = call_result["risk_score"]
                        mic_live_state["risk_level"] = call_result["risk_level"]
                        mic_live_state["max_fraud_prob"] = call_result["max_fraud_prob"]
                        mic_live_state["avg_fraud_prob"] = call_result["avg_fraud_prob"]
                        mic_live_state["status"] = f"Chunk {chunk_id} skipped (silence)"

                        print_live_update(
                            chunk_info=chunk_info,
                            transcript="[SKIPPED - SILENCE]",
                            segment_results=[],
                            used_segments=used_segments,
                            call_result=call_result,
                            latency=latency
                        )

                        buffer_audio = buffer_audio[step_samples:]
                        chunk_id += 1
                        continue

                    transcript = transcribe_chunk(asr_model, current_chunk, SAMPLE_RATE)

                    if transcript.strip():
                        segments = split_text_into_segments(transcript, max_words=30)
                        segment_results = predict_segments(
                            classifier, tokenizer, segments, chunk_id
                        )
                        all_segment_results.extend(segment_results)

                        latest_lexicon_cues = summarize_lexicon_cues(segment_results)
                        mic_live_state["latest_lexicon_cues"] = latest_lexicon_cues

                        mic_live_state["transcript"] = (
                            mic_live_state["transcript"] + " " + transcript
                        ).strip()
                    else:
                        segment_results = []
                        mic_live_state["latest_lexicon_cues"] = []

                    used_segments, call_result = update_live_decision(all_segment_results)

                    latency = time.time() - chunk_start

                    mic_live_state["final_label"] = call_result["final_label"]
                    mic_live_state["risk_score"] = call_result["risk_score"]
                    mic_live_state["risk_level"] = call_result["risk_level"]
                    mic_live_state["max_fraud_prob"] = call_result["max_fraud_prob"]
                    mic_live_state["avg_fraud_prob"] = call_result["avg_fraud_prob"]
                    mic_live_state["status"] = f"Chunk {chunk_id} analyzed"

                    print_live_update(
                        chunk_info=chunk_info,
                        transcript=transcript,
                        segment_results=segment_results,
                        used_segments=used_segments,
                        call_result=call_result,
                        latency=latency
                    )

                    buffer_audio = buffer_audio[step_samples:]
                    chunk_id += 1

    except KeyboardInterrupt:
        print("\n[INFO] Microphone recording stopped by user.")
        mic_live_state["status"] = "Stopped by user"

    except Exception as e:
        print(f"[ERROR] Microphone pipeline failed: {e}")
        mic_live_state["error"] = str(e)
        mic_live_state["status"] = "Error"

    total_time = time.time() - total_start

    if all_segment_results:
        _, call_result = update_live_decision(all_segment_results)

        final_lexicon_cues = summarize_lexicon_cues(all_segment_results)
        mic_live_state["final_lexicon_cues"] = final_lexicon_cues

        print("\n" + "#" * 60)
        print("FINAL MICROPHONE REAL-TIME DECISION")
        print(f"FINAL LABEL : {call_result['final_label']}")
        print(f"FINAL SCORE : {call_result['risk_score']:.4f}")
        print(f"FINAL RISK  : {call_result['risk_level']}")
        print(f"TOTAL TIME  : {total_time:.2f} sec")

        print("\n[FINAL LEXICON-BASED EXPLANATION]")
        if final_lexicon_cues:
             for cue in final_lexicon_cues:
                 print(
                 f"  - {cue['keyword']} | type={cue['type']} | count={cue['count']}"
                 )
        else:
              print("  No fraud-related lexicon cues detected.")

        print("#" * 60)

        mic_live_state["final_label"] = call_result["final_label"]
        mic_live_state["risk_score"] = call_result["risk_score"]
        mic_live_state["risk_level"] = call_result["risk_level"]
        mic_live_state["max_fraud_prob"] = call_result["max_fraud_prob"]
        mic_live_state["avg_fraud_prob"] = call_result["avg_fraud_prob"]
        mic_live_state["status"] = "Final decision ready"
    else:
        print("[INFO] No valid speech was processed.")
        mic_live_state["status"] = "No valid speech processed"

    mic_live_state["running"] = False

    return {
    "final_label": mic_live_state["final_label"],
    "risk_score": mic_live_state["risk_score"],
    "risk_level": mic_live_state["risk_level"],
    "transcript": mic_live_state["transcript"],
    "final_lexicon_cues": mic_live_state["final_lexicon_cues"],
    "latest_lexicon_cues": mic_live_state["latest_lexicon_cues"]
}


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    MODE = "mic"   # "file" or "mic"
    AUDIO_PATH = r"C:\Users\LAYAL\Downloads\Telegram Desktop\GP22\GP22\GP2\audio\Safe_call_1517.wav"

    print("[INFO] Loading models...")
    asr_model, tokenizer, classifier = load_models()

    if MODE == "file":
        run_file_realtime_pipeline(
            audio_path=AUDIO_PATH,
            asr_model=asr_model,
            tokenizer=tokenizer,
            classifier=classifier
        )

    elif MODE == "mic":
        run_microphone_realtime_pipeline(
            asr_model=asr_model,
            tokenizer=tokenizer,
            classifier=classifier
        )

    else:
        print("[ERROR] MODE must be either 'file' or 'mic'")