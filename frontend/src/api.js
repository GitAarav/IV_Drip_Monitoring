const API_URL = "http://localhost:8000/api";

export async function getSessions() {
  const response = await fetch(
    `${API_URL}/sessions`
  );

  if (!response.ok) {
    throw new Error("Failed to load sessions");
  }

  return response.json();
}


export async function getSession(sessionId) {
  const response = await fetch(
    `${API_URL}/sessions/${sessionId}`
  );

  if (!response.ok) {
    throw new Error("Failed to load session");
  }

  return response.json();
}


export async function getFusion(sessionId) {
  const response = await fetch(
    `${API_URL}/sessions/${sessionId}/fusion`
  );

  if (!response.ok) {
    throw new Error("Failed to load fusion data");
  }

  return response.json();
}