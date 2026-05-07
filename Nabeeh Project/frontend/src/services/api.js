const API_URL = "http://127.0.0.1:8000";

async function apiFetch(endpoint, options = {}) {
  const response = await fetch(`${API_URL}${endpoint}`, options);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "API Error");
  }

  return data;
}

export async function fetchHistory() {
  const data = await apiFetch("/history");
  return data.items || [];
}

export async function startMicDetection() {
  return await apiFetch("/start-mic-detection", {
    method: "POST",
  });
}

export async function fetchMicStatus() {
  return await apiFetch("/mic-status");
}

export async function stopMicDetection() {
  return await apiFetch("/stop-mic-detection", {
    method: "POST",
  });
}

export async function analyzeAudioFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_URL}/predict-audio`, {
    method: "POST",
    body: formData,
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }

  return data;
}