# Nabeeh Project

Nabeeh is a real-time Arabic voice fraud detection system that integrates Faster-Whisper ASR with a fine-tuned MARBERT model to analyze Arabic phone conversations and detect fraudulent behavior in real time. The system supports real-time microphone analysis, Arabic speech transcription, fraud classification, dynamic risk scoring, explainability visualization, and real-time fraud alerts.

The project consists of a FastAPI backend for the fraud detection pipeline, a React + Vite frontend user interface, and a MARBERT-based fraud classification model.

---
Due to GitHub file size limitations, the trained MARBERT model weights (`model.safetensors`) are hosted externally. Download the model file from the following link:

[Download model.safetensors](https://drive.google.com/file/d/1lQ6ixIiVlw6kAGUWBGMFfpGlEDZlRTzl/view?usp=sharing)

After downloading, place the file inside:

model/MARBERT_final/

To run the project, first install the required Python libraries using:

```bash
pip install -r requirements.txt
```
Then run the FastAPI backend server using:
```bash
uvicorn backend.main:app --reload
```
Next, navigate to the frontend directory:
```bash
cd frontend
```
Install the frontend dependencies:
```bash
npm install
```
Finally, run the frontend development server:
```bash
npm run dev
```
